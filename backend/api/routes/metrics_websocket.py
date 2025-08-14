"""
WebSocket Routes for Real-time Metrics Streaming

WebSocket endpoints for streaming real-time performance metrics
to dashboard clients with filtering and subscription management.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Set, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import BaseModel, Field

from backend.api.websocket_manager import WebSocketManager
from backend.services.real_time_metrics_collector import (
    RealTimeMetricsCollector,
    MetricType
)

logger = logging.getLogger(__name__)

# Router for WebSocket endpoints
router = APIRouter()

# Global instances (will be injected by main app)
metrics_collector: Optional[RealTimeMetricsCollector] = None
websocket_manager: Optional[WebSocketManager] = None

# Active subscriptions tracking
active_subscriptions: Dict[str, Set[MetricType]] = {}


class MetricsSubscriptionRequest(BaseModel):
    """Request model for metrics subscription."""
    action: str = Field(..., regex="^(subscribe|unsubscribe)$")
    metric_types: List[str] = Field(default_factory=list)
    update_interval: Optional[float] = Field(1.0, ge=0.1, le=60.0)  # seconds


class MetricsWebSocketHandler:
    """Handles WebSocket connections for real-time metrics streaming."""

    def __init__(self, client_id: str, websocket: WebSocket):
        self.client_id = client_id
        self.websocket = websocket
        self.subscriptions: Set[MetricType] = set()
        self.update_interval = 1.0  # seconds
        self.streaming_task: Optional[asyncio.Task] = None
        self.last_update = datetime.now()

    async def handle_connection(self):
        """Handle the WebSocket connection lifecycle."""
        try:
            # Accept connection
            await self.websocket.accept()
            logger.info(f"Metrics WebSocket client {self.client_id} connected")

            # Register for metric updates
            if metrics_collector:
                metrics_collector.subscribe_to_metrics(self._on_metrics_update)

            # Send initial welcome message
            await self.send_message({
                "type": "connected",
                "client_id": self.client_id,
                "message": "Connected to real-time metrics stream",
                "timestamp": datetime.now().isoformat(),
                "available_metrics": [metric.value for metric in MetricType]
            })

            # Start listening for client messages
            while True:
                try:
                    # Wait for client message
                    data = await self.websocket.receive_text()
                    await self.handle_client_message(json.loads(data))
                except json.JSONDecodeError as e:
                    await self.send_error(f"Invalid JSON: {e}")
                except Exception as e:
                    logger.error(f"Error handling client message: {e}")
                    await self.send_error(f"Message handling error: {e}")

        except WebSocketDisconnect:
            logger.info(f"Metrics WebSocket client {self.client_id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket error for client {self.client_id}: {e}")
        finally:
            await self.cleanup()

    async def handle_client_message(self, message: Dict[str, Any]):
        """Handle incoming client messages."""
        try:
            message_type = message.get("type")

            if message_type == "subscribe":
                await self.handle_subscription(message)
            elif message_type == "unsubscribe":
                await self.handle_unsubscription(message)
            elif message_type == "get_current":
                await self.handle_current_metrics_request()
            elif message_type == "ping":
                await self.send_message({"type": "pong", "timestamp": datetime.now().isoformat()})
            else:
                await self.send_error(f"Unknown message type: {message_type}")

        except Exception as e:
            logger.error(f"Error handling client message: {e}")
            await self.send_error(f"Error processing message: {e}")

    async def handle_subscription(self, message: Dict[str, Any]):
        """Handle subscription requests."""
        try:
            metric_types = message.get("metric_types", [])
            update_interval = message.get("update_interval", 1.0)

            # Validate and convert metric types
            new_subscriptions = set()
            for metric_str in metric_types:
                try:
                    metric_type = MetricType(metric_str.lower())
                    new_subscriptions.add(metric_type)
                except ValueError:
                    await self.send_error(f"Invalid metric type: {metric_str}")
                    return

            # Update subscriptions
            self.subscriptions = new_subscriptions
            self.update_interval = max(0.1, min(60.0, update_interval))

            # Track global subscriptions
            active_subscriptions[self.client_id] = self.subscriptions

            # Start streaming if not already running
            if self.subscriptions and not self.streaming_task:
                self.streaming_task = asyncio.create_task(self._stream_metrics())
            elif not self.subscriptions and self.streaming_task:
                self.streaming_task.cancel()
                self.streaming_task = None

            await self.send_message({
                "type": "subscription_updated",
                "subscribed_metrics": [m.value for m in self.subscriptions],
                "update_interval": self.update_interval,
                "timestamp": datetime.now().isoformat()
            })

            logger.info(f"Client {self.client_id} subscribed to {len(self.subscriptions)} metrics")

        except Exception as e:
            logger.error(f"Error handling subscription: {e}")
            await self.send_error(f"Subscription error: {e}")

    async def handle_unsubscription(self, message: Dict[str, Any]):
        """Handle unsubscription requests."""
        try:
            metric_types = message.get("metric_types", [])

            if not metric_types:
                # Unsubscribe from all
                self.subscriptions.clear()
            else:
                # Remove specific subscriptions
                for metric_str in metric_types:
                    try:
                        metric_type = MetricType(metric_str.lower())
                        self.subscriptions.discard(metric_type)
                    except ValueError:
                        await self.send_error(f"Invalid metric type: {metric_str}")
                        return

            # Update global tracking
            active_subscriptions[self.client_id] = self.subscriptions

            # Stop streaming if no subscriptions
            if not self.subscriptions and self.streaming_task:
                self.streaming_task.cancel()
                self.streaming_task = None

            await self.send_message({
                "type": "unsubscription_updated",
                "remaining_subscriptions": [m.value for m in self.subscriptions],
                "timestamp": datetime.now().isoformat()
            })

            logger.info(f"Client {self.client_id} unsubscribed, {len(self.subscriptions)} remaining")

        except Exception as e:
            logger.error(f"Error handling unsubscription: {e}")
            await self.send_error(f"Unsubscription error: {e}")

    async def handle_current_metrics_request(self):
        """Handle request for current metrics snapshot."""
        try:
            if not metrics_collector:
                await self.send_error("Metrics collector not available")
                return

            current_metrics = metrics_collector.get_current_metrics()
            health_summary = metrics_collector.get_system_health_summary()

            # Filter to subscribed metrics if any
            if self.subscriptions:
                filtered_metrics = {
                    metric_type.value: data
                    for metric_type, data in current_metrics.items()
                    if metric_type in self.subscriptions
                }
            else:
                filtered_metrics = current_metrics

            await self.send_message({
                "type": "current_metrics",
                "metrics": filtered_metrics,
                "health_summary": health_summary,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Error handling current metrics request: {e}")
            await self.send_error(f"Current metrics error: {e}")

    async def _stream_metrics(self):
        """Background task to stream metrics at specified interval."""
        try:
            while self.subscriptions:
                if not metrics_collector:
                    await asyncio.sleep(self.update_interval)
                    continue

                # Get current metrics
                current_metrics = metrics_collector.get_current_metrics()

                # Filter to subscribed metrics
                filtered_metrics = {}
                for metric_type in self.subscriptions:
                    if metric_type.value in current_metrics:
                        filtered_metrics[metric_type.value] = current_metrics[metric_type.value]

                # Send update if we have data
                if filtered_metrics:
                    await self.send_message({
                        "type": "metrics_update",
                        "metrics": filtered_metrics,
                        "timestamp": datetime.now().isoformat()
                    })
                    self.last_update = datetime.now()

                await asyncio.sleep(self.update_interval)

        except asyncio.CancelledError:
            logger.debug(f"Metrics streaming cancelled for client {self.client_id}")
        except Exception as e:
            logger.error(f"Error in metrics streaming for client {self.client_id}: {e}")

    async def _on_metrics_update(self, metrics_update: Dict[MetricType, Dict[str, Any]]):
        """Handle metrics update from collector."""
        try:
            # Only process if we have active subscriptions
            if not self.subscriptions:
                return

            # Filter to subscribed metrics
            filtered_update = {}
            for metric_type, data in metrics_update.items():
                if metric_type in self.subscriptions and data:
                    filtered_update[metric_type.value] = data

            # Send update if relevant
            if filtered_update:
                await self.send_message({
                    "type": "live_metrics_update",
                    "metrics": filtered_update,
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Error handling metrics update: {e}")

    async def send_message(self, message: Dict[str, Any]):
        """Send message to WebSocket client."""
        try:
            await self.websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send message to client {self.client_id}: {e}")
            raise

    async def send_error(self, error_message: str):
        """Send error message to client."""
        try:
            await self.send_message({
                "type": "error",
                "error": error_message,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    async def cleanup(self):
        """Clean up resources when connection closes."""
        try:
            # Cancel streaming task
            if self.streaming_task and not self.streaming_task.done():
                self.streaming_task.cancel()
                try:
                    await self.streaming_task
                except asyncio.CancelledError:
                    pass

            # Unsubscribe from metrics updates
            if metrics_collector:
                metrics_collector.unsubscribe_from_metrics(self._on_metrics_update)

            # Remove from global tracking
            active_subscriptions.pop(self.client_id, None)

            logger.debug(f"Cleaned up metrics WebSocket handler for client {self.client_id}")

        except Exception as e:
            logger.error(f"Error during cleanup for client {self.client_id}: {e}")


@router.websocket("/ws/metrics/{client_id}")
async def metrics_websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time metrics streaming.

    Client can send messages to:
    - Subscribe to specific metric types
    - Request current metrics snapshot
    - Ping for connection health
    """
    handler = MetricsWebSocketHandler(client_id, websocket)
    await handler.handle_connection()


@router.websocket("/ws/system-health/{client_id}")
async def system_health_websocket(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for system health monitoring with alerts.
    """
    try:
        await websocket.accept()
        logger.info(f"System health WebSocket client {client_id} connected")

        while True:
            try:
                if not metrics_collector:
                    await asyncio.sleep(5)
                    continue

                # Get system health summary
                health_summary = metrics_collector.get_system_health_summary()

                # Get current alerts/critical metrics
                current_metrics = metrics_collector.get_current_metrics()
                alerts = []

                # Check for critical conditions
                if MetricType.SYSTEM.value in current_metrics:
                    sys_data = current_metrics[MetricType.SYSTEM.value]

                    if sys_data.get('cpu_percent', 0) > 90:
                        alerts.append({
                            "type": "cpu",
                            "severity": "critical",
                            "message": f"CPU usage at {sys_data['cpu_percent']:.1f}%",
                            "value": sys_data['cpu_percent']
                        })

                    if sys_data.get('memory_percent', 0) > 90:
                        alerts.append({
                            "type": "memory",
                            "severity": "critical",
                            "message": f"Memory usage at {sys_data['memory_percent']:.1f}%",
                            "value": sys_data['memory_percent']
                        })

                # Send health update
                await websocket.send_text(json.dumps({
                    "type": "health_update",
                    "health_summary": health_summary,
                    "alerts": alerts,
                    "timestamp": datetime.now().isoformat()
                }))

                # Update every 5 seconds for health monitoring
                await asyncio.sleep(5)

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in system health WebSocket: {e}")
                await asyncio.sleep(5)

    except Exception as e:
        logger.error(f"System health WebSocket error for client {client_id}: {e}")
    finally:
        logger.info(f"System health WebSocket client {client_id} disconnected")


@router.get("/metrics/websocket/stats")
async def get_websocket_stats():
    """Get statistics about active WebSocket connections and subscriptions."""
    try:
        stats = {
            "total_connections": len(active_subscriptions),
            "connections_by_metrics": {},
            "most_popular_metrics": {},
            "total_subscriptions": 0
        }

        # Count subscriptions by metric type
        metric_counts = {}
        for client_id, subscriptions in active_subscriptions.items():
            stats["total_subscriptions"] += len(subscriptions)
            for metric in subscriptions:
                metric_counts[metric.value] = metric_counts.get(metric.value, 0) + 1

        stats["most_popular_metrics"] = dict(sorted(
            metric_counts.items(),
            key=lambda x: x[1],
            reverse=True
        ))

        # Connections by metric count
        for client_id, subscriptions in active_subscriptions.items():
            count = len(subscriptions)
            stats["connections_by_metrics"][count] = stats["connections_by_metrics"].get(count, 0) + 1

        return {
            "status": "success",
            "message": "WebSocket statistics retrieved",
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting WebSocket stats: {e}")
        return {
            "status": "error",
            "message": f"Failed to get WebSocket stats: {e}",
            "timestamp": datetime.now().isoformat()
        }


def initialize_metrics_websocket(
    collector_instance: RealTimeMetricsCollector,
    ws_manager: WebSocketManager
):
    """Initialize metrics WebSocket services."""
    global metrics_collector, websocket_manager
    metrics_collector = collector_instance
    websocket_manager = ws_manager
    logger.info("Metrics WebSocket endpoints initialized")