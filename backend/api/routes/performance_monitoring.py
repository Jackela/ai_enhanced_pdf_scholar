"""
Performance Monitoring API Routes

FastAPI routes for accessing all performance monitoring, caching telemetry,
APM, alerting, and optimization capabilities.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.services.integrated_performance_monitor import IntegratedPerformanceMonitor
from backend.services.cache_telemetry_service import CacheLayer
from backend.services.performance_alerting_service import AlertSeverity, WarmingPriority

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/performance", tags=["performance"])

# Performance monitor instance (will be injected)
performance_monitor: Optional[IntegratedPerformanceMonitor] = None


# ============================================================================
# Request/Response Models
# ============================================================================

class PerformanceOverview(BaseModel):
    """Performance overview response model."""
    timestamp: datetime
    system_health_score: float
    status: str
    cache_health: Dict[str, Any]
    apm_metrics: Dict[str, Any] 
    active_alerts: int
    recommendations: int


class CacheAnalytics(BaseModel):
    """Cache analytics response model."""
    timestamp: datetime
    layer_metrics: Dict[str, Dict[str, Any]]
    health_assessment: Dict[str, Any]
    optimization_recommendations: List[Dict[str, Any]]
    warming_candidates: List[Dict[str, Any]]


class AlertRuleCreate(BaseModel):
    """Create alert rule request model."""
    name: str
    description: str
    metric_name: str
    condition: str = Field(..., regex="^(>|>=|<|<=|==)$")
    threshold_value: float
    severity: AlertSeverity
    evaluation_window_minutes: int = Field(5, ge=1, le=60)
    min_data_points: int = Field(3, ge=1, le=20)
    cooldown_minutes: int = Field(15, ge=1, le=120)
    enabled: bool = True
    tags: Optional[Dict[str, str]] = None
    custom_message_template: Optional[str] = None


class WarmingJobCreate(BaseModel):
    """Create cache warming job request model."""
    cache_layer: CacheLayer
    keys: List[str] = Field(..., min_items=1, max_items=1000)
    priority: WarmingPriority = WarmingPriority.MEDIUM
    scheduled_for: Optional[datetime] = None


# ============================================================================
# Dependency Injection
# ============================================================================

def get_performance_monitor() -> IntegratedPerformanceMonitor:
    """Get performance monitor instance."""
    if performance_monitor is None:
        raise HTTPException(
            status_code=503,
            detail="Performance monitoring not initialized"
        )
    return performance_monitor


# ============================================================================
# Performance Overview Routes
# ============================================================================

@router.get("/overview", response_model=Dict[str, Any])
async def get_performance_overview(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get comprehensive performance overview."""
    try:
        real_time_metrics = monitor.get_real_time_metrics()
        return {
            "status": "success",
            "data": real_time_metrics
        }
    except Exception as e:
        logger.error(f"Error getting performance overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_system_health(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get system health status."""
    try:
        health_status = monitor.get_service_health_status()
        return {
            "status": "success",
            "data": health_status
        }
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/comprehensive")
async def get_comprehensive_report(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get comprehensive performance report from all services."""
    try:
        report = monitor.get_comprehensive_performance_report()
        return {
            "status": "success",
            "data": report
        }
    except Exception as e:
        logger.error(f"Error getting comprehensive report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends")
async def get_performance_trends(
    hours_back: int = Query(24, ge=1, le=168),  # Max 1 week
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get performance trends over time."""
    try:
        trends = monitor.get_performance_trends(hours_back)
        return {
            "status": "success", 
            "data": trends
        }
    except Exception as e:
        logger.error(f"Error getting performance trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Cache Analytics Routes
# ============================================================================

@router.get("/cache/analytics")
async def get_cache_analytics(
    layer: Optional[CacheLayer] = None,
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get detailed cache analytics."""
    try:
        cache_data = monitor.cache_telemetry.get_dashboard_data()
        
        if layer:
            # Filter to specific layer
            layer_data = cache_data.get("layer_metrics", {}).get(layer.value)
            if not layer_data:
                raise HTTPException(status_code=404, detail=f"Layer {layer.value} not found")
            cache_data = {"layer_metrics": {layer.value: layer_data}}
        
        return {
            "status": "success",
            "data": cache_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cache analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/recommendations")
async def get_cache_recommendations(
    layer: Optional[CacheLayer] = None,
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get cache optimization recommendations."""
    try:
        recommendations = monitor.cache_optimization.get_optimization_recommendations(layer)
        return {
            "status": "success",
            "data": recommendations
        }
    except Exception as e:
        logger.error(f"Error getting cache recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/patterns")
async def get_cache_patterns(
    layer: Optional[CacheLayer] = None,
    limit: int = Query(100, ge=1, le=500),
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get identified cache access patterns."""
    try:
        patterns = monitor.cache_optimization.get_access_patterns(layer, limit)
        return {
            "status": "success",
            "data": patterns
        }
    except Exception as e:
        logger.error(f"Error getting cache patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/warming/candidates")
async def get_warming_candidates(
    layer: Optional[CacheLayer] = None,
    limit: int = Query(50, ge=1, le=200),
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get cache warming candidates."""
    try:
        candidates = monitor.cache_optimization.get_warming_candidates(layer, limit)
        return {
            "status": "success",
            "data": candidates
        }
    except Exception as e:
        logger.error(f"Error getting warming candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/warming/jobs")
async def create_warming_job(
    job_request: WarmingJobCreate,
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Create a cache warming job."""
    try:
        job_id = monitor.cache_optimization.schedule_warming_job(
            cache_layer=job_request.cache_layer,
            keys=job_request.keys,
            priority=job_request.priority,
            scheduled_for=job_request.scheduled_for
        )
        
        return {
            "status": "success",
            "data": {
                "job_id": job_id,
                "message": f"Warming job scheduled for {len(job_request.keys)} keys"
            }
        }
    except Exception as e:
        logger.error(f"Error creating warming job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/warming/jobs/{job_id}")
async def get_warming_job_status(
    job_id: str,
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get status of a cache warming job."""
    try:
        job_status = monitor.cache_optimization.get_warming_job_status(job_id)
        if not job_status:
            raise HTTPException(status_code=404, detail="Warming job not found")
        
        return {
            "status": "success",
            "data": job_status
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting warming job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# APM and Tracing Routes
# ============================================================================

@router.get("/apm/summary")
async def get_apm_summary(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get APM performance summary."""
    try:
        summary = monitor.amp.get_performance_summary()
        return {
            "status": "success",
            "data": summary
        }
    except Exception as e:
        logger.error(f"Error getting APM summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apm/traces/slow")
async def get_slow_traces(
    threshold_ms: float = Query(1000, ge=100, le=30000),
    limit: int = Query(50, ge=1, le=200),
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get slow traces."""
    try:
        slow_traces = monitor.amp.get_slow_traces(threshold_ms, limit)
        
        # Convert traces to serializable format
        traces_data = []
        for trace in slow_traces:
            traces_data.append({
                "trace_id": trace.trace_id,
                "trace_type": trace.trace_type.value,
                "duration_ms": trace.duration_ms,
                "has_errors": trace.has_errors,
                "error_count": trace.error_count,
                "user_id": trace.user_id,
                "session_id": trace.session_id,
                "root_operation": trace.root_span.operation_name,
                "start_time": trace.root_span.start_time.isoformat()
            })
        
        return {
            "status": "success",
            "data": traces_data
        }
    except Exception as e:
        logger.error(f"Error getting slow traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apm/traces/errors")
async def get_error_traces(
    limit: int = Query(50, ge=1, le=200),
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get traces with errors."""
    try:
        error_traces = monitor.amp.get_error_traces(limit)
        
        # Convert traces to serializable format
        traces_data = []
        for trace in error_traces:
            traces_data.append({
                "trace_id": trace.trace_id,
                "trace_type": trace.trace_type.value,
                "duration_ms": trace.duration_ms,
                "error_count": trace.error_count,
                "user_id": trace.user_id,
                "session_id": trace.session_id,
                "root_operation": trace.root_span.operation_name,
                "start_time": trace.root_span.start_time.isoformat(),
                "root_error": trace.root_span.error
            })
        
        return {
            "status": "success",
            "data": traces_data
        }
    except Exception as e:
        logger.error(f"Error getting error traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apm/traces/{trace_id}")
async def get_trace_details(
    trace_id: str,
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get detailed information for a specific trace."""
    try:
        trace_details = monitor.dashboard_service._get_trace_details(trace_id)
        if not trace_details:
            raise HTTPException(status_code=404, detail="Trace not found")
        
        return {
            "status": "success",
            "data": trace_details
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trace details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Alerting Routes
# ============================================================================

@router.get("/alerts")
async def get_active_alerts(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get active performance alerts."""
    try:
        alerts = monitor.alerting_service.get_active_alerts()
        return {
            "status": "success",
            "data": alerts
        }
    except Exception as e:
        logger.error(f"Error getting active alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/history")
async def get_alert_history(
    hours_back: int = Query(24, ge=1, le=168),
    severity: Optional[List[AlertSeverity]] = Query(None),
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get alert history."""
    try:
        history = monitor.alerting_service.get_alert_history(hours_back, severity)
        return {
            "status": "success",
            "data": history
        }
    except Exception as e:
        logger.error(f"Error getting alert history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/statistics")
async def get_alert_statistics(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get alert statistics."""
    try:
        stats = monitor.alerting_service.get_alert_statistics()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error getting alert statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/rules")
async def create_alert_rule(
    rule_request: AlertRuleCreate,
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Create a new alert rule."""
    try:
        from backend.services.performance_alerting_service import AlertRule
        import uuid
        
        rule = AlertRule(
            rule_id=str(uuid.uuid4()),
            name=rule_request.name,
            description=rule_request.description,
            metric_name=rule_request.metric_name,
            condition=rule_request.condition,
            threshold_value=rule_request.threshold_value,
            severity=rule_request.severity,
            evaluation_window_minutes=rule_request.evaluation_window_minutes,
            min_data_points=rule_request.min_data_points,
            cooldown_minutes=rule_request.cooldown_minutes,
            enabled=rule_request.enabled,
            tags=rule_request.tags or {},
            custom_message_template=rule_request.custom_message_template
        )
        
        success = monitor.alerting_service.add_alert_rule(rule)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create alert rule")
        
        return {
            "status": "success",
            "data": {
                "rule_id": rule.rule_id,
                "message": "Alert rule created successfully"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating alert rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str,
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Acknowledge an active alert."""
    try:
        success = monitor.alerting_service.acknowledge_alert(alert_id, acknowledged_by)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")
        
        return {
            "status": "success",
            "data": {
                "message": f"Alert {alert_id} acknowledged by {acknowledged_by}"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_note: str = "",
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Manually resolve an active alert."""
    try:
        success = monitor.alerting_service.resolve_alert(alert_id, resolution_note)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "status": "success",
            "data": {
                "message": f"Alert {alert_id} resolved"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Analysis and Optimization Routes
# ============================================================================

@router.post("/analyze/comprehensive")
async def trigger_comprehensive_analysis(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Trigger comprehensive performance analysis."""
    try:
        result = await monitor.trigger_comprehensive_analysis()
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error triggering comprehensive analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize/emergency")
async def trigger_emergency_optimization(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Trigger emergency optimization procedures."""
    try:
        result = await monitor.emergency_optimization()
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error triggering emergency optimization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/optimize/trigger")
async def trigger_cache_optimization(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Trigger immediate cache optimization analysis."""
    try:
        result = monitor.cache_optimization.trigger_immediate_analysis()
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error triggering cache optimization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Dashboard and WebSocket Routes
# ============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def get_performance_dashboard(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> HTMLResponse:
    """Get the performance monitoring dashboard HTML page."""
    try:
        return monitor.dashboard_service.get_dashboard_page()
    except Exception as e:
        logger.error(f"Error getting dashboard page: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
):
    """WebSocket endpoint for real-time dashboard updates."""
    try:
        await monitor.dashboard_service.handle_websocket_connection(websocket)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


@router.get("/dashboard/data")
async def get_dashboard_data(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Get dashboard data via HTTP API."""
    try:
        data = monitor.dashboard_service.get_api_metrics()
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Export Routes
# ============================================================================

@router.get("/export/telemetry")
async def export_telemetry_data(
    format: str = Query("json", regex="^(json)$"),
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Export telemetry data."""
    try:
        data = monitor.cache_telemetry.export_telemetry_report()
        return {
            "status": "success",
            "data": data,
            "export_metadata": {
                "format": format,
                "generated_at": datetime.utcnow().isoformat(),
                "total_events": len(monitor.cache_telemetry.events)
            }
        }
    except Exception as e:
        logger.error(f"Error exporting telemetry data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/dashboard")
async def export_dashboard_data(
    format: str = Query("json", regex="^(json)$"),
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Export dashboard data."""
    try:
        data = monitor.dashboard_service.get_export_data(format)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error exporting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Service Management Routes
# ============================================================================

@router.post("/services/start")
async def start_performance_monitoring(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Start performance monitoring services."""
    try:
        await monitor.start_monitoring()
        return {
            "status": "success",
            "data": {
                "message": "Performance monitoring services started successfully"
            }
        }
    except Exception as e:
        logger.error(f"Error starting performance monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/services/stop")
async def stop_performance_monitoring(
    monitor: IntegratedPerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """Stop performance monitoring services."""
    try:
        await monitor.stop_monitoring()
        return {
            "status": "success",
            "data": {
                "message": "Performance monitoring services stopped successfully"
            }
        }
    except Exception as e:
        logger.error(f"Error stopping performance monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Initialization
# ============================================================================

def initialize_performance_monitor(monitor_instance: IntegratedPerformanceMonitor):
    """Initialize the performance monitor instance for dependency injection."""
    global performance_monitor
    performance_monitor = monitor_instance
    logger.info("Performance monitor initialized for API routes")