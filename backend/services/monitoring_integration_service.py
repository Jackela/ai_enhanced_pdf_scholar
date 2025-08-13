"""
Monitoring Integration Service

Integrates the real-time metrics collector with existing monitoring
infrastructure including WebSocket manager and performance monitor.
"""

import asyncio
import logging
from typing import Optional
from backend.services.real_time_metrics_collector import RealTimeMetricsCollector
from backend.services.integrated_performance_monitor import IntegratedPerformanceMonitor
from backend.api.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class MonitoringIntegrationService:
    """
    Service that integrates real-time metrics collection with existing
    monitoring infrastructure and provides unified monitoring capabilities.
    """
    
    def __init__(
        self,
        websocket_manager: Optional[WebSocketManager] = None,
        integrated_monitor: Optional[IntegratedPerformanceMonitor] = None
    ):
        self.websocket_manager = websocket_manager
        self.integrated_monitor = integrated_monitor
        
        # Initialize metrics collector with existing services
        self.metrics_collector = RealTimeMetricsCollector(
            websocket_manager=websocket_manager,
            integrated_monitor=integrated_monitor
        )
        
        self._integration_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("MonitoringIntegrationService initialized")
    
    async def start_integrated_monitoring(self):
        """Start integrated monitoring with all services."""
        if self._running:
            logger.warning("Integrated monitoring already running")
            return
        
        try:
            self._running = True
            
            # Start the real-time metrics collector
            await self.metrics_collector.start_collection()
            
            # Start integrated performance monitor if available
            if self.integrated_monitor:
                await self.integrated_monitor.start_monitoring()
            
            # Start integration bridge
            self._integration_task = asyncio.create_task(self._integration_bridge())
            
            logger.info("Integrated monitoring started successfully")
            
        except Exception as e:
            logger.error(f"Error starting integrated monitoring: {e}")
            await self.stop_integrated_monitoring()
            raise
    
    async def stop_integrated_monitoring(self):
        """Stop integrated monitoring."""
        if not self._running:
            return
        
        self._running = False
        
        try:
            # Stop integration bridge
            if self._integration_task and not self._integration_task.done():
                self._integration_task.cancel()
                try:
                    await self._integration_task
                except asyncio.CancelledError:
                    pass
            
            # Stop metrics collector
            await self.metrics_collector.stop_collection()
            
            # Stop integrated performance monitor if available
            if self.integrated_monitor:
                await self.integrated_monitor.stop_monitoring()
            
            logger.info("Integrated monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping integrated monitoring: {e}")
    
    async def _integration_bridge(self):
        """Bridge between different monitoring services."""
        while self._running:
            try:
                # Enhanced WebSocket integration
                if self.websocket_manager:
                    await self._integrate_websocket_metrics()
                
                # Performance monitor integration
                if self.integrated_monitor:
                    await self._integrate_performance_monitor()
                
                await asyncio.sleep(5)  # Integration check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in integration bridge: {e}")
                await asyncio.sleep(10)  # Back off on error
    
    async def _integrate_websocket_metrics(self):
        """Integrate WebSocket metrics with enhanced functionality."""
        try:
            # Get WebSocket stats
            ws_stats = self.websocket_manager.get_stats()
            
            # Enhanced RAG task metrics
            if ws_stats.get('rag_streaming'):
                rag_metrics = ws_stats['rag_streaming']
                
                # Detect potential issues
                pending_tasks = rag_metrics.get('pending_tasks', 0)
                processing_tasks = rag_metrics.get('processing_tasks', 0)
                failed_tasks = rag_metrics.get('failed_tasks', 0)
                
                # Alert on high queue buildup
                if pending_tasks > 10:
                    await self._send_alert(
                        'websocket',
                        'warning',
                        f'High RAG task queue: {pending_tasks} pending tasks',
                        value=pending_tasks,
                        threshold=10
                    )
                
                # Alert on high failure rate
                total_tasks = rag_metrics.get('total_tasks', 0)
                if total_tasks > 0:
                    failure_rate = (failed_tasks / total_tasks) * 100
                    if failure_rate > 10:
                        await self._send_alert(
                            'websocket',
                            'error',
                            f'High RAG task failure rate: {failure_rate:.1f}%',
                            value=failure_rate,
                            threshold=10
                        )
                
                # Connection monitoring
                active_connections = ws_stats.get('active_connections', 0)
                if active_connections > 50:
                    await self._send_alert(
                        'websocket',
                        'warning',
                        f'High WebSocket connection count: {active_connections}',
                        value=active_connections,
                        threshold=50
                    )
            
        except Exception as e:
            logger.error(f"Error integrating WebSocket metrics: {e}")
    
    async def _integrate_performance_monitor(self):
        """Integrate with performance monitor for enhanced metrics."""
        try:
            # Get comprehensive performance data
            performance_data = self.integrated_monitor.get_real_time_metrics()
            
            # Integrate cache telemetry
            if hasattr(self.integrated_monitor, 'cache_telemetry'):
                cache_data = self.integrated_monitor.cache_telemetry.get_dashboard_data()
                
                # Monitor cache hit rates
                for layer, metrics in cache_data.get('layer_metrics', {}).items():
                    hit_rate = metrics.get('hit_ratio', 0)
                    if hit_rate < 70:
                        await self._send_alert(
                            'cache',
                            'warning',
                            f'Low cache hit rate in {layer}: {hit_rate:.1f}%',
                            value=hit_rate,
                            threshold=70
                        )
            
            # Integrate APM data
            if hasattr(self.integrated_monitor, 'apm_service'):
                apm_data = self.integrated_monitor.amp.get_performance_summary()
                
                # Monitor slow operations
                if apm_data.get('avg_response_time_ms', 0) > 1000:
                    await self._send_alert(
                        'api',
                        'warning',
                        f'Slow API responses: {apm_data["avg_response_time_ms"]:.1f}ms',
                        value=apm_data['avg_response_time_ms'],
                        threshold=1000
                    )
            
        except Exception as e:
            logger.error(f"Error integrating performance monitor: {e}")
    
    async def _send_alert(self, alert_type: str, severity: str, message: str, value: float = None, threshold: float = None):
        """Send alert through WebSocket channels."""
        try:
            if self.websocket_manager:
                alert_data = {
                    'type': 'system_alert',
                    'alert': {
                        'type': alert_type,
                        'severity': severity,
                        'message': message,
                        'timestamp': asyncio.get_event_loop().time(),
                        'value': value,
                        'threshold': threshold
                    }
                }
                
                await self.websocket_manager.broadcast_json(alert_data)
                
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
    
    def get_metrics_collector(self) -> RealTimeMetricsCollector:
        """Get the metrics collector instance."""
        return self.metrics_collector
    
    def get_integration_status(self) -> dict:
        """Get status of monitoring integration."""
        return {
            'running': self._running,
            'metrics_collector_active': self.metrics_collector is not None,
            'websocket_manager_active': self.websocket_manager is not None,
            'performance_monitor_active': self.integrated_monitor is not None,
            'services_status': {
                'metrics_collection': 'running' if self._running else 'stopped',
                'websocket_integration': 'enabled' if self.websocket_manager else 'disabled',
                'performance_integration': 'enabled' if self.integrated_monitor else 'disabled'
            }
        }
    
    async def trigger_manual_collection(self) -> dict:
        """Manually trigger metrics collection and return current state."""
        try:
            current_metrics = self.metrics_collector.get_current_metrics()
            health_summary = self.metrics_collector.get_system_health_summary()
            
            # Get additional data from integrated services
            additional_data = {}
            
            if self.websocket_manager:
                additional_data['websocket_stats'] = self.websocket_manager.get_stats()
            
            if self.integrated_monitor:
                additional_data['performance_status'] = self.integrated_monitor.get_service_health_status()
            
            return {
                'current_metrics': current_metrics,
                'health_summary': health_summary,
                'integration_status': self.get_integration_status(),
                'additional_data': additional_data
            }
            
        except Exception as e:
            logger.error(f"Error in manual collection: {e}")
            return {
                'error': str(e),
                'integration_status': self.get_integration_status()
            }


# Global integration service instance
integration_service: Optional[MonitoringIntegrationService] = None


def initialize_monitoring_integration(
    websocket_manager: Optional[WebSocketManager] = None,
    integrated_monitor: Optional[IntegratedPerformanceMonitor] = None
) -> MonitoringIntegrationService:
    """Initialize the monitoring integration service."""
    global integration_service
    
    integration_service = MonitoringIntegrationService(
        websocket_manager=websocket_manager,
        integrated_monitor=integrated_monitor
    )
    
    logger.info("Monitoring integration service initialized globally")
    return integration_service


def get_monitoring_integration() -> Optional[MonitoringIntegrationService]:
    """Get the global monitoring integration service instance."""
    return integration_service