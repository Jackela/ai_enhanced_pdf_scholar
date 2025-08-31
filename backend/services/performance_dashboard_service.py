"""
Real-time Performance Dashboard Service

Provides real-time performance dashboards, metrics visualization,
and interactive performance monitoring for the AI Enhanced PDF Scholar system.
"""

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketState

from backend.services.apm_service import APMService
from backend.services.cache_telemetry_service import CacheTelemetryService
from backend.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


# ============================================================================
# Dashboard Data Models
# ============================================================================

class DashboardMetrics:
    """Real-time dashboard metrics."""

    def __init__(
        self,
        apm_service: APMService,
        cache_telemetry: CacheTelemetryService,
        metrics_service: MetricsService
    ):
        self.apm = apm_service
        self.cache_telemetry = cache_telemetry
        self.metrics = metrics_service

    def get_overview_metrics(self) -> dict[str, Any]:
        """Get high-level overview metrics."""
        # Get latest performance snapshot
        latest_snapshot = (
            self.apm.performance_snapshots[-1]
            if self.apm.performance_snapshots else None
        )

        if not latest_snapshot:
            return {
                "status": "no_data",
                "message": "No performance data available"
            }

        # Get cache health
        cache_health = self.cache_telemetry.assess_cache_health()

        # Get active alerts
        active_alerts = [
            alert for alert in self.amp.alerts
            if not alert.resolved
        ]

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system_health": {
                "overall_score": cache_health.overall_score,
                "status": cache_health.status,
                "active_alerts": len(active_alerts)
            },
            "performance": {
                "requests_per_second": latest_snapshot.requests_per_second,
                "avg_response_time_ms": latest_snapshot.avg_response_time_ms,
                "p95_response_time_ms": latest_snapshot.p95_response_time_ms,
                "error_rate_percent": latest_snapshot.error_rate_percent
            },
            "resources": {
                "cpu_percent": latest_snapshot.cpu_percent,
                "memory_percent": latest_snapshot.memory_percent,
                "cache_hit_rate": latest_snapshot.cache_hit_rate_percent
            },
            "alerts": [
                {
                    "severity": alert.severity,
                    "title": alert.title,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in active_alerts[-5:]  # Last 5 alerts
            ]
        }

    def get_detailed_performance_metrics(self) -> dict[str, Any]:
        """Get detailed performance metrics for charts."""
        # Get last hour of performance snapshots
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        recent_snapshots = [
            snapshot for snapshot in self.apm.performance_snapshots
            if snapshot.timestamp >= cutoff_time
        ]

        if not recent_snapshots:
            return {"error": "No recent performance data"}

        # Format for time series charts
        timestamps = [s.timestamp.isoformat() for s in recent_snapshots]

        return {
            "timeline": timestamps,
            "response_times": {
                "avg": [s.avg_response_time_ms for s in recent_snapshots],
                "p50": [s.p50_response_time_ms for s in recent_snapshots],
                "p95": [s.p95_response_time_ms for s in recent_snapshots],
                "p99": [s.p99_response_time_ms for s in recent_snapshots]
            },
            "throughput": {
                "requests_per_second": [s.requests_per_second for s in recent_snapshots]
            },
            "error_rates": {
                "error_rate_percent": [s.error_rate_percent for s in recent_snapshots]
            },
            "resources": {
                "cpu_percent": [s.cpu_percent for s in recent_snapshots],
                "memory_percent": [s.memory_percent for s in recent_snapshots]
            },
            "cache": {
                "hit_rate_percent": [s.cache_hit_rate_percent for s in recent_snapshots],
                "miss_rate_percent": [s.cache_miss_rate_percent for s in recent_snapshots]
            }
        }

    def get_cache_analytics(self) -> dict[str, Any]:
        """Get detailed cache analytics."""
        return self.cache_telemetry.get_dashboard_data()

    def get_trace_analytics(self) -> dict[str, Any]:
        """Get trace analytics for APM dashboard."""
        # Get slow traces
        slow_traces = self.apm.get_slow_traces(threshold_ms=500, limit=10)

        # Get error traces
        error_traces = self.apm.get_error_traces(limit=10)

        # Get trace distribution by operation
        operation_stats = {}
        for trace in list(self.amp.traces)[-1000:]:  # Last 1000 traces
            op_name = trace.root_span.operation_name
            if op_name not in operation_stats:
                operation_stats[op_name] = {
                    "count": 0,
                    "total_duration": 0,
                    "errors": 0
                }

            operation_stats[op_name]["count"] += 1
            if trace.duration_ms:
                operation_stats[op_name]["total_duration"] += trace.duration_ms
            if trace.has_errors:
                operation_stats[op_name]["errors"] += 1

        # Calculate averages
        for op_name, stats in operation_stats.items():
            stats["avg_duration_ms"] = (
                stats["total_duration"] / stats["count"]
                if stats["count"] > 0 else 0
            )
            stats["error_rate_percent"] = (
                (stats["errors"] / stats["count"]) * 100
                if stats["count"] > 0 else 0
            )

        return {
            "slow_traces": [
                {
                    "trace_id": trace.trace_id,
                    "operation": trace.root_span.operation_name,
                    "duration_ms": trace.duration_ms,
                    "start_time": trace.root_span.start_time.isoformat(),
                    "has_errors": trace.has_errors
                }
                for trace in slow_traces
            ],
            "error_traces": [
                {
                    "trace_id": trace.trace_id,
                    "operation": trace.root_span.operation_name,
                    "duration_ms": trace.duration_ms,
                    "error_count": trace.error_count,
                    "start_time": trace.root_span.start_time.isoformat()
                }
                for trace in error_traces
            ],
            "operation_statistics": sorted(
                [
                    {"operation": op, **stats}
                    for op, stats in operation_stats.items()
                ],
                key=lambda x: x["avg_duration_ms"],
                reverse=True
            )[:20]  # Top 20 operations
        }


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.connection_metadata: dict[WebSocket, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, client_info: dict[str, Any] = None):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = client_info or {}
        logger.info(f"WebSocket connection established. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.connection_metadata.pop(websocket, None)
            logger.info(f"WebSocket connection closed. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_text(json.dumps(message, default=str))
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}")
                self.disconnect(websocket)

    async def broadcast(self, message: dict[str, Any]):
        """Broadcast a message to all connected WebSockets."""
        if not self.active_connections:
            return

        disconnected_connections = []

        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(json.dumps(message, default=str))
                else:
                    disconnected_connections.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected_connections.append(connection)

        # Clean up disconnected connections
        for connection in disconnected_connections:
            self.disconnect(connection)

    async def send_to_subscribers(self, message: dict[str, Any], subscription_type: str):
        """Send message to subscribers of a specific type."""
        for connection in self.active_connections:
            metadata = self.connection_metadata.get(connection, {})
            subscriptions = metadata.get("subscriptions", [])

            if subscription_type in subscriptions:
                await self.send_personal_message(message, connection)


# ============================================================================
# Performance Dashboard Service
# ============================================================================

class PerformanceDashboardService:
    """
    Real-time performance dashboard service with WebSocket support.
    """

    def __init__(
        self,
        apm_service: APMService,
        cache_telemetry: CacheTelemetryService,
        metrics_service: MetricsService
    ):
        self.apm = apm_service
        self.cache_telemetry = cache_telemetry
        self.metrics = metrics_service

        self.dashboard_metrics = DashboardMetrics(apm_service, cache_telemetry, metrics_service)
        self.connection_manager = ConnectionManager()

        # Background task for real-time updates
        self._update_task: asyncio.Task | None = None
        self._running = False

    async def start_real_time_updates(self):
        """Start background task for real-time updates."""
        if not self._running:
            self._running = True
            self._update_task = asyncio.create_task(self._real_time_update_loop())
            logger.info("Real-time dashboard updates started")

    async def stop_real_time_updates(self):
        """Stop background task for real-time updates."""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            logger.info("Real-time dashboard updates stopped")

    async def _real_time_update_loop(self):
        """Background loop for sending real-time updates."""
        while self._running:
            try:
                # Send overview metrics every 5 seconds
                overview_data = self.dashboard_metrics.get_overview_metrics()
                await self.connection_manager.send_to_subscribers(
                    {
                        "type": "overview_update",
                        "data": overview_data
                    },
                    "overview"
                )

                await asyncio.sleep(5)

                # Send detailed metrics every 30 seconds
                detailed_data = self.dashboard_metrics.get_detailed_performance_metrics()
                await self.connection_manager.send_to_subscribers(
                    {
                        "type": "performance_update",
                        "data": detailed_data
                    },
                    "performance"
                )

                # Send cache analytics every 60 seconds
                cache_data = self.dashboard_metrics.get_cache_analytics()
                await self.connection_manager.send_to_subscribers(
                    {
                        "type": "cache_update",
                        "data": cache_data
                    },
                    "cache"
                )

                await asyncio.sleep(25)  # Total 30 seconds between detailed updates

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in real-time update loop: {e}")
                await asyncio.sleep(5)

    # ========================================================================
    # WebSocket Handlers
    # ========================================================================

    async def handle_websocket_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection."""
        try:
            # Accept connection
            await self.connection_manager.connect(websocket)

            # Send initial data
            initial_data = {
                "type": "initial_data",
                "data": {
                    "overview": self.dashboard_metrics.get_overview_metrics(),
                    "performance": self.dashboard_metrics.get_detailed_performance_metrics(),
                    "cache": self.dashboard_metrics.get_cache_analytics(),
                    "traces": self.dashboard_metrics.get_trace_analytics()
                }
            }
            await self.connection_manager.send_personal_message(initial_data, websocket)

            # Handle client messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self._handle_client_message(websocket, message)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    await self.connection_manager.send_personal_message(
                        {"type": "error", "message": str(e)},
                        websocket
                    )

        except WebSocketDisconnect:
            pass
        finally:
            self.connection_manager.disconnect(websocket)

    async def _handle_client_message(self, websocket: WebSocket, message: dict[str, Any]):
        """Handle message from WebSocket client."""
        message_type = message.get("type")

        if message_type == "subscribe":
            # Handle subscription to specific updates
            subscriptions = message.get("subscriptions", [])
            metadata = self.connection_manager.connection_metadata.get(websocket, {})
            metadata["subscriptions"] = subscriptions
            self.connection_manager.connection_metadata[websocket] = metadata

            await self.connection_manager.send_personal_message(
                {"type": "subscription_confirmed", "subscriptions": subscriptions},
                websocket
            )

        elif message_type == "get_trace_details":
            # Get detailed trace information
            trace_id = message.get("trace_id")
            trace_details = self._get_trace_details(trace_id)

            await self.connection_manager.send_personal_message(
                {"type": "trace_details", "data": trace_details},
                websocket
            )

        elif message_type == "get_cache_recommendations":
            # Get cache optimization recommendations
            recommendations = self.cache_telemetry.generate_optimization_recommendations()

            await self.connection_manager.send_personal_message(
                {
                    "type": "cache_recommendations",
                    "data": [asdict(rec) for rec in recommendations]
                },
                websocket
            )

        elif message_type == "trigger_cache_analysis":
            # Trigger cache analysis
            analysis = {
                "health": self.cache_telemetry.assess_cache_health(),
                "optimization": self.cache_telemetry.generate_optimization_recommendations(),
                "warming_candidates": {
                    layer.value: self.cache_telemetry.identify_cache_warming_candidates(layer)
                    for layer in self.cache_telemetry.CacheLayer
                }
            }

            await self.connection_manager.send_personal_message(
                {"type": "cache_analysis_result", "data": analysis},
                websocket
            )

    def _get_trace_details(self, trace_id: str) -> dict[str, Any] | None:
        """Get detailed information for a specific trace."""
        for trace in self.apm.traces:
            if trace.trace_id == trace_id:
                return {
                    "trace_id": trace.trace_id,
                    "trace_type": trace.trace_type.value,
                    "duration_ms": trace.duration_ms,
                    "has_errors": trace.has_errors,
                    "error_count": trace.error_count,
                    "user_id": trace.user_id,
                    "session_id": trace.session_id,
                    "root_span": asdict(trace.root_span),
                    "spans": [asdict(span) for span in trace.spans],
                    "span_tree": self._build_span_tree(trace)
                }

        return None

    def _build_span_tree(self, trace) -> dict[str, Any]:
        """Build hierarchical span tree for visualization."""
        def build_node(span, children):
            return {
                "span_id": span.span_id,
                "operation_name": span.operation_name,
                "span_type": span.span_type.value,
                "duration_ms": span.duration_ms,
                "start_time": span.start_time.isoformat(),
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "tags": span.tags,
                "error": span.error,
                "children": children
            }

        # Build parent-child relationships
        span_map = {trace.root_span.span_id: trace.root_span}
        for span in trace.spans:
            span_map[span.span_id] = span

        # Build tree recursively
        def build_children(parent_span_id):
            children = []
            for span in trace.spans:
                if span.parent_span_id == parent_span_id:
                    children.append(build_node(span, build_children(span.span_id)))
            return children

        return build_node(trace.root_span, build_children(trace.root_span.span_id))

    # ========================================================================
    # Dashboard HTML Generation
    # ========================================================================

    def generate_dashboard_html(self) -> str:
        """Generate HTML for the performance dashboard."""
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AI Enhanced PDF Scholar - Performance Dashboard</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }
                .dashboard-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }
                .widget {
                    background: white;
                    border-radius: 8px;
                    padding: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .widget h3 {
                    margin-top: 0;
                    color: #333;
                    border-bottom: 2px solid #667eea;
                    padding-bottom: 10px;
                }
                .metric-card {
                    display: inline-block;
                    background: #f8f9fa;
                    border-left: 4px solid #667eea;
                    padding: 15px;
                    margin: 10px;
                    border-radius: 4px;
                    min-width: 150px;
                }
                .metric-value {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                }
                .metric-label {
                    color: #666;
                    font-size: 12px;
                    text-transform: uppercase;
                }
                .status-healthy { color: #28a745; }
                .status-degraded { color: #ffc107; }
                .status-critical { color: #dc3545; }
                .alert-item {
                    padding: 10px;
                    margin: 5px 0;
                    border-radius: 4px;
                    border-left: 4px solid #dc3545;
                    background: #f8d7da;
                }
                .chart-container {
                    position: relative;
                    height: 300px;
                    margin-top: 20px;
                }
                .connection-status {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 10px;
                    border-radius: 4px;
                    color: white;
                }
                .connected { background: #28a745; }
                .disconnected { background: #dc3545; }
                .reconnecting { background: #ffc107; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Performance Dashboard</h1>
                <p>Real-time monitoring for AI Enhanced PDF Scholar</p>
                <div id="connection-status" class="connection-status disconnected">Connecting...</div>
            </div>

            <div class="dashboard-grid">
                <!-- System Overview -->
                <div class="widget">
                    <h3>System Overview</h3>
                    <div id="overview-metrics">
                        <div class="metric-card">
                            <div class="metric-value" id="requests-per-second">--</div>
                            <div class="metric-label">Requests/Second</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value" id="avg-response-time">--</div>
                            <div class="metric-label">Avg Response (ms)</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value" id="error-rate">--</div>
                            <div class="metric-label">Error Rate (%)</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value" id="cpu-usage">--</div>
                            <div class="metric-label">CPU Usage (%)</div>
                        </div>
                    </div>
                </div>

                <!-- Cache Performance -->
                <div class="widget">
                    <h3>Cache Performance</h3>
                    <div id="cache-metrics">
                        <div class="metric-card">
                            <div class="metric-value" id="cache-hit-rate">--</div>
                            <div class="metric-label">Hit Rate (%)</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value" id="cache-health-score">--</div>
                            <div class="metric-label">Health Score</div>
                        </div>
                    </div>
                </div>

                <!-- Active Alerts -->
                <div class="widget">
                    <h3>Active Alerts</h3>
                    <div id="alerts-list">
                        <p>No active alerts</p>
                    </div>
                </div>

                <!-- Response Time Chart -->
                <div class="widget">
                    <h3>Response Time Trends</h3>
                    <div class="chart-container">
                        <canvas id="response-time-chart"></canvas>
                    </div>
                </div>

                <!-- Throughput Chart -->
                <div class="widget">
                    <h3>Throughput</h3>
                    <div class="chart-container">
                        <canvas id="throughput-chart"></canvas>
                    </div>
                </div>

                <!-- Cache Analytics -->
                <div class="widget">
                    <h3>Cache Layer Analysis</h3>
                    <div class="chart-container">
                        <canvas id="cache-analysis-chart"></canvas>
                    </div>
                </div>
            </div>

            <script>
                class PerformanceDashboard {
                    constructor() {
                        this.socket = null;
                        this.charts = {};
                        this.reconnectAttempts = 0;
                        this.maxReconnectAttempts = 10;
                        this.init();
                    }

                    init() {
                        this.setupWebSocket();
                        this.initCharts();
                    }

                    setupWebSocket() {
                        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
                        const wsUrl = `${protocol}//${location.host}/ws/dashboard`;

                        this.socket = new WebSocket(wsUrl);

                        this.socket.onopen = () => {
                            console.log('WebSocket connected');
                            this.updateConnectionStatus('connected');
                            this.reconnectAttempts = 0;

                            // Subscribe to all updates
                            this.socket.send(JSON.stringify({
                                type: 'subscribe',
                                subscriptions: ['overview', 'performance', 'cache', 'traces']
                            }));
                        };

                        this.socket.onmessage = (event) => {
                            const message = JSON.parse(event.data);
                            this.handleMessage(message);
                        };

                        this.socket.onclose = () => {
                            console.log('WebSocket disconnected');
                            this.updateConnectionStatus('disconnected');
                            this.attemptReconnect();
                        };

                        this.socket.onerror = (error) => {
                            console.error('WebSocket error:', error);
                            this.updateConnectionStatus('disconnected');
                        };
                    }

                    attemptReconnect() {
                        if (this.reconnectAttempts < this.maxReconnectAttempts) {
                            this.reconnectAttempts++;
                            this.updateConnectionStatus('reconnecting');

                            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
                            setTimeout(() => this.setupWebSocket(), delay);
                        }
                    }

                    updateConnectionStatus(status) {
                        const statusElement = document.getElementById('connection-status');
                        statusElement.className = `connection-status ${status}`;
                        statusElement.textContent = status === 'connected' ? 'Connected' :
                                                 status === 'reconnecting' ? 'Reconnecting...' : 'Disconnected';
                    }

                    handleMessage(message) {
                        switch (message.type) {
                            case 'initial_data':
                                this.updateOverview(message.data.overview);
                                this.updatePerformanceCharts(message.data.performance);
                                this.updateCacheAnalytics(message.data.cache);
                                break;
                            case 'overview_update':
                                this.updateOverview(message.data);
                                break;
                            case 'performance_update':
                                this.updatePerformanceCharts(message.data);
                                break;
                            case 'cache_update':
                                this.updateCacheAnalytics(message.data);
                                break;
                            default:
                                console.log('Unknown message type:', message.type);
                        }
                    }

                    updateOverview(data) {
                        if (data.performance) {
                            document.getElementById('requests-per-second').textContent =
                                data.performance.requests_per_second?.toFixed(1) || '--';
                            document.getElementById('avg-response-time').textContent =
                                data.performance.avg_response_time_ms?.toFixed(0) || '--';
                            document.getElementById('error-rate').textContent =
                                data.performance.error_rate_percent?.toFixed(2) || '--';
                        }

                        if (data.resources) {
                            document.getElementById('cpu-usage').textContent =
                                data.resources.cpu_percent?.toFixed(1) || '--';
                            document.getElementById('cache-hit-rate').textContent =
                                data.resources.cache_hit_rate?.toFixed(1) || '--';
                        }

                        if (data.system_health) {
                            document.getElementById('cache-health-score').textContent =
                                data.system_health.overall_score?.toFixed(0) || '--';
                        }

                        // Update alerts
                        const alertsList = document.getElementById('alerts-list');
                        if (data.alerts && data.alerts.length > 0) {
                            alertsList.innerHTML = data.alerts.map(alert => `
                                <div class="alert-item">
                                    <strong>${alert.severity.toUpperCase()}</strong>: ${alert.title}
                                    <br><small>${new Date(alert.timestamp).toLocaleString()}</small>
                                </div>
                            `).join('');
                        } else {
                            alertsList.innerHTML = '<p>No active alerts</p>';
                        }
                    }

                    updatePerformanceCharts(data) {
                        if (!data.timeline) return;

                        // Update response time chart
                        const responseChart = this.charts.responseTime;
                        if (responseChart) {
                            responseChart.data.labels = data.timeline.map(t => new Date(t).toLocaleTimeString());
                            responseChart.data.datasets[0].data = data.response_times.avg;
                            responseChart.data.datasets[1].data = data.response_times.p95;
                            responseChart.update('none');
                        }

                        // Update throughput chart
                        const throughputChart = this.charts.throughput;
                        if (throughputChart) {
                            throughputChart.data.labels = data.timeline.map(t => new Date(t).toLocaleTimeString());
                            throughputChart.data.datasets[0].data = data.throughput.requests_per_second;
                            throughputChart.update('none');
                        }
                    }

                    updateCacheAnalytics(data) {
                        if (!data.layer_metrics) return;

                        const cacheChart = this.charts.cacheAnalysis;
                        if (cacheChart) {
                            const layers = Object.keys(data.layer_metrics);
                            const hitRates = layers.map(layer => data.layer_metrics[layer].hit_rate || 0);

                            cacheChart.data.labels = layers;
                            cacheChart.data.datasets[0].data = hitRates;
                            cacheChart.update('none');
                        }
                    }

                    initCharts() {
                        // Response Time Chart
                        const responseCtx = document.getElementById('response-time-chart').getContext('2d');
                        this.charts.responseTime = new Chart(responseCtx, {
                            type: 'line',
                            data: {
                                labels: [],
                                datasets: [{
                                    label: 'Average',
                                    data: [],
                                    borderColor: '#667eea',
                                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                                    tension: 0.4
                                }, {
                                    label: 'P95',
                                    data: [],
                                    borderColor: '#f093fb',
                                    backgroundColor: 'rgba(240, 147, 251, 0.1)',
                                    tension: 0.4
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                scales: {
                                    y: {
                                        beginAtZero: true,
                                        title: { display: true, text: 'Response Time (ms)' }
                                    }
                                }
                            }
                        });

                        // Throughput Chart
                        const throughputCtx = document.getElementById('throughput-chart').getContext('2d');
                        this.charts.throughput = new Chart(throughputCtx, {
                            type: 'line',
                            data: {
                                labels: [],
                                datasets: [{
                                    label: 'Requests/Second',
                                    data: [],
                                    borderColor: '#764ba2',
                                    backgroundColor: 'rgba(118, 75, 162, 0.1)',
                                    tension: 0.4
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                scales: {
                                    y: {
                                        beginAtZero: true,
                                        title: { display: true, text: 'Requests/Second' }
                                    }
                                }
                            }
                        });

                        // Cache Analysis Chart
                        const cacheCtx = document.getElementById('cache-analysis-chart').getContext('2d');
                        this.charts.cacheAnalysis = new Chart(cacheCtx, {
                            type: 'bar',
                            data: {
                                labels: [],
                                datasets: [{
                                    label: 'Hit Rate %',
                                    data: [],
                                    backgroundColor: 'rgba(102, 126, 234, 0.8)'
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                scales: {
                                    y: {
                                        beginAtZero: true,
                                        max: 100,
                                        title: { display: true, text: 'Hit Rate (%)' }
                                    }
                                }
                            }
                        });
                    }
                }

                // Initialize dashboard when page loads
                document.addEventListener('DOMContentLoaded', () => {
                    new PerformanceDashboard();
                });
            </script>
        </body>
        </html>
        """
        return html_content

    # ========================================================================
    # HTTP Endpoints
    # ========================================================================

    def get_dashboard_page(self) -> HTMLResponse:
        """Get the dashboard HTML page."""
        return HTMLResponse(content=self.generate_dashboard_html())

    def get_api_metrics(self) -> dict[str, Any]:
        """Get metrics via HTTP API."""
        return {
            "overview": self.dashboard_metrics.get_overview_metrics(),
            "performance": self.dashboard_metrics.get_detailed_performance_metrics(),
            "cache": self.dashboard_metrics.get_cache_analytics(),
            "traces": self.dashboard_metrics.get_trace_analytics()
        }

    def get_export_data(self, format: str = "json") -> dict[str, Any]:
        """Export dashboard data for external tools."""
        data = self.get_api_metrics()

        # Add additional export metadata
        data["export_metadata"] = {
            "generated_at": datetime.utcnow().isoformat(),
            "format": format,
            "service_version": "2.0.0",
            "export_type": "performance_dashboard"
        }

        return data
