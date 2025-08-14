"""
Rate Limiting Administration and Monitoring Endpoints
Provides admin interface for monitoring and managing rate limiting
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

try:
    from ..middleware.rate_limit_monitor import get_monitor, RateLimitMetrics
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False


# Response models
class RateLimitMetricsResponse(BaseModel):
    """Rate limiting metrics response."""
    total_requests: int
    successful_requests: int
    rate_limited_requests: int
    error_requests: int
    unique_ips: int
    avg_response_time: float
    top_endpoints: List[tuple]
    top_ips: List[tuple]
    rate_limit_effectiveness: float
    success_rate: float
    error_rate: float

    @classmethod
    def from_metrics(cls, metrics: 'RateLimitMetrics') -> 'RateLimitMetricsResponse':
        """Create response from metrics object."""
        total = metrics.total_requests or 1  # Avoid division by zero

        return cls(
            total_requests=metrics.total_requests,
            successful_requests=metrics.successful_requests,
            rate_limited_requests=metrics.rate_limited_requests,
            error_requests=metrics.error_requests,
            unique_ips=metrics.unique_ips,
            avg_response_time=metrics.avg_response_time,
            top_endpoints=metrics.top_endpoints,
            top_ips=metrics.top_ips,
            rate_limit_effectiveness=metrics.rate_limit_effectiveness,
            success_rate=metrics.successful_requests / total * 100,
            error_rate=metrics.error_requests / total * 100
        )


class IPAnalysisResponse(BaseModel):
    """IP analysis response."""
    client_ip: str
    total_requests: int
    rate_limited_requests: int
    rate_limited_percentage: float
    endpoints_accessed: List[str]
    request_rate_per_minute: float
    first_seen: Optional[float]
    last_seen: Optional[float]
    suspicion_score: Optional[int] = None


class EndpointAnalysisResponse(BaseModel):
    """Endpoint analysis response."""
    endpoint: str
    total_requests: int
    rate_limited_requests: int
    rate_limited_percentage: float
    unique_ips: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    top_ips: List[tuple]


class SuspiciousIPResponse(BaseModel):
    """Suspicious IP response."""
    client_ip: str
    total_requests: int
    rate_limited_requests: int
    rate_limited_percentage: float
    request_rate_per_minute: float
    unique_endpoints: int
    unique_user_agents: int
    suspicion_score: int
    first_seen: float
    last_seen: float


# Security dependency (simplified - in production, use proper auth)
async def require_admin():
    """Require admin privileges for rate limiting management."""
    # In production, implement proper authentication/authorization
    # For now, this is a placeholder
    return True


# Router setup
router = APIRouter(dependencies=[Depends(require_admin)])

if not MONITORING_AVAILABLE:
    # Provide placeholder responses when monitoring is not available

    @router.get("/rate-limit/status")
    async def get_rate_limit_status():
        """Get rate limiting system status."""
        return {
            "status": "disabled",
            "message": "Rate limiting monitoring is not available",
            "monitoring_available": False
        }

else:
    # Full monitoring endpoints when available

    @router.get("/rate-limit/status")
    async def get_rate_limit_status():
        """Get rate limiting system status."""
        monitor = get_monitor()
        metrics = monitor.get_metrics(window_minutes=60)

        return {
            "status": "active",
            "monitoring_available": True,
            "uptime_hours": 24,  # Placeholder
            "total_events_recorded": len(monitor._events),
            "current_window_requests": metrics.total_requests,
            "current_window_rate_limited": metrics.rate_limited_requests,
            "effectiveness_percentage": metrics.rate_limit_effectiveness * 100
        }

    @router.get("/rate-limit/metrics", response_model=RateLimitMetricsResponse)
    async def get_rate_limit_metrics(
        window_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes")
    ):
        """Get rate limiting metrics for specified time window."""
        monitor = get_monitor()
        metrics = monitor.get_metrics(window_minutes=window_minutes)

        return RateLimitMetricsResponse.from_metrics(metrics)

    @router.get("/rate-limit/ip/{client_ip}", response_model=IPAnalysisResponse)
    async def get_ip_analysis(
        client_ip: str,
        window_minutes: int = Query(60, ge=1, le=1440, description="Analysis window in minutes")
    ):
        """Get detailed analysis for a specific IP address."""
        monitor = get_monitor()
        analysis = monitor.get_ip_metrics(client_ip, window_minutes)

        if "error" in analysis:
            raise HTTPException(status_code=404, detail=analysis["error"])

        return IPAnalysisResponse(**analysis)

    @router.get("/rate-limit/endpoint", response_model=EndpointAnalysisResponse)
    async def get_endpoint_analysis(
        endpoint: str = Query(..., description="Endpoint path to analyze"),
        window_minutes: int = Query(60, ge=1, le=1440, description="Analysis window in minutes")
    ):
        """Get detailed analysis for a specific endpoint."""
        monitor = get_monitor()
        analysis = monitor.get_endpoint_metrics(endpoint, window_minutes)

        if "error" in analysis:
            raise HTTPException(status_code=404, detail=analysis["error"])

        return EndpointAnalysisResponse(**analysis)

    @router.get("/rate-limit/suspicious-ips", response_model=List[SuspiciousIPResponse])
    async def get_suspicious_ips(
        window_minutes: int = Query(60, ge=1, le=1440, description="Analysis window in minutes"),
        min_requests: int = Query(50, ge=10, le=1000, description="Minimum requests to be considered"),
        limit: int = Query(20, ge=1, le=100, description="Maximum number of results")
    ):
        """Get list of suspicious IP addresses based on behavior patterns."""
        monitor = get_monitor()
        suspicious_ips = monitor.get_suspicious_ips(
            window_minutes=window_minutes,
            min_requests=min_requests
        )

        # Convert to response models and limit results
        results = []
        for ip_data in suspicious_ips[:limit]:
            results.append(SuspiciousIPResponse(**ip_data))

        return results

    @router.get("/rate-limit/top-endpoints")
    async def get_top_endpoints(
        window_minutes: int = Query(60, ge=1, le=1440, description="Analysis window in minutes"),
        limit: int = Query(10, ge=1, le=50, description="Number of top endpoints to return")
    ):
        """Get most frequently accessed endpoints."""
        monitor = get_monitor()
        metrics = monitor.get_metrics(window_minutes=window_minutes)

        return {
            "window_minutes": window_minutes,
            "top_endpoints": metrics.top_endpoints[:limit],
            "total_unique_endpoints": len(metrics.top_endpoints)
        }

    @router.get("/rate-limit/top-ips")
    async def get_top_ips(
        window_minutes: int = Query(60, ge=1, le=1440, description="Analysis window in minutes"),
        limit: int = Query(10, ge=1, le=50, description="Number of top IPs to return")
    ):
        """Get most active IP addresses."""
        monitor = get_monitor()
        metrics = monitor.get_metrics(window_minutes=window_minutes)

        return {
            "window_minutes": window_minutes,
            "top_ips": metrics.top_ips[:limit],
            "total_unique_ips": metrics.unique_ips
        }

    @router.post("/rate-limit/export")
    async def export_rate_limit_data(
        window_minutes: Optional[int] = Query(None, ge=1, le=10080, description="Export window in minutes"),
        filename: str = Query("rate_limit_export.json", description="Export filename")
    ):
        """Export rate limiting data to JSON file."""
        monitor = get_monitor()

        try:
            monitor.export_events(filename, window_minutes)
            return {
                "message": f"Rate limiting data exported to {filename}",
                "filename": filename,
                "window_minutes": window_minutes
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

    @router.delete("/rate-limit/cleanup")
    async def cleanup_old_events(
        hours_to_keep: int = Query(24, ge=1, le=168, description="Hours of data to keep")
    ):
        """Clean up old rate limiting events to free memory."""
        monitor = get_monitor()

        old_count = len(monitor._events)
        monitor.clear_old_events(hours_to_keep)
        new_count = len(monitor._events)

        return {
            "message": f"Cleaned up old events",
            "events_before": old_count,
            "events_after": new_count,
            "events_removed": old_count - new_count,
            "hours_kept": hours_to_keep
        }

    @router.get("/rate-limit/health")
    async def get_rate_limit_health():
        """Get health status of rate limiting system."""
        monitor = get_monitor()

        # Get recent metrics to assess health
        metrics_5m = monitor.get_metrics(window_minutes=5)
        metrics_60m = monitor.get_metrics(window_minutes=60)

        # Calculate health indicators
        recent_error_rate = 0
        if metrics_5m.total_requests > 0:
            recent_error_rate = metrics_5m.error_requests / metrics_5m.total_requests * 100

        rate_limiting_active = metrics_5m.rate_limited_requests > 0
        high_load = metrics_5m.total_requests > 1000  # 1000 requests in 5 minutes

        # Determine overall health
        health_status = "healthy"
        if recent_error_rate > 5:
            health_status = "degraded"
        if recent_error_rate > 20:
            health_status = "unhealthy"

        health_score = max(0, 100 - recent_error_rate - (10 if high_load else 0))

        return {
            "status": health_status,
            "health_score": health_score,
            "rate_limiting_active": rate_limiting_active,
            "high_load_detected": high_load,
            "recent_error_rate": recent_error_rate,
            "metrics_5m": {
                "total_requests": metrics_5m.total_requests,
                "rate_limited": metrics_5m.rate_limited_requests,
                "errors": metrics_5m.error_requests,
                "unique_ips": metrics_5m.unique_ips
            },
            "metrics_60m": {
                "total_requests": metrics_60m.total_requests,
                "rate_limited": metrics_60m.rate_limited_requests,
                "errors": metrics_60m.error_requests,
                "unique_ips": metrics_60m.unique_ips
            }
        }

    @router.get("/rate-limit/alerts")
    async def get_recent_alerts():
        """Get recent rate limiting alerts and warnings."""
        # This would typically integrate with an alerting system
        # For now, return placeholder data
        return {
            "alerts": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "severity": "warning",
                    "type": "high_rate_limiting",
                    "message": "High rate limiting detected for IP 192.168.1.100",
                    "details": {
                        "client_ip": "192.168.1.100",
                        "rate_limited_percentage": 85.5,
                        "total_requests": 120
                    }
                }
            ],
            "alert_count": 1,
            "last_24_hours": 3
        }


# Always provide configuration endpoints
@router.get("/rate-limit/config")
async def get_rate_limit_config():
    """Get current rate limiting configuration."""
    # Import here to avoid circular imports
    from ..rate_limit_config import get_rate_limit_config

    config = get_rate_limit_config()

    return {
        "default_limit": {
            "requests": config.default_limit.requests,
            "window_seconds": config.default_limit.window
        },
        "global_ip_limit": {
            "requests": config.global_ip_limit.requests,
            "window_seconds": config.global_ip_limit.window
        },
        "endpoint_limits": {
            endpoint: {
                "requests": rule.requests,
                "window_seconds": rule.window
            }
            for endpoint, rule in config.endpoint_limits.items()
        },
        "redis_enabled": config.redis_url is not None,
        "monitoring_enabled": config.enable_monitoring,
        "bypass_ips": list(config.bypass_ips),
        "bypass_user_agents": list(config.bypass_user_agents)
    }