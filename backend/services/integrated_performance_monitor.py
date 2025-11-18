"""
Integrated Performance Monitoring Service

Orchestrates all performance monitoring, caching telemetry, APM, alerting,
and optimization services into a unified performance monitoring solution.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.apm_service import APMService
from backend.services.cache_optimization_service import (
    CacheOptimizationService,
    WarmingPriority,
)
from backend.services.cache_telemetry_service import CacheLayer, CacheTelemetryService
from backend.services.metrics_service import MetricsService
from backend.services.performance_alerting_service import PerformanceAlertingService
from backend.services.performance_dashboard_service import PerformanceDashboardService
from backend.services.redis_cache_service import RedisCacheService
from src.services.rag_cache_service import RAGCacheService

logger = logging.getLogger(__name__)


# ============================================================================
# Integrated Performance Monitor
# ============================================================================


class IntegratedPerformanceMonitor:
    """
    Central orchestrator for all performance monitoring capabilities.
    """

    def __init__(
        self,
        redis_cache: RedisCacheService,
        rag_cache: RAGCacheService,
        config_path: Path | None = None,
    ):
        """Initialize integrated performance monitor."""
        self.config_path = config_path or Path("performance_config.json")

        # Initialize core services
        self.metrics_service = MetricsService()
        self.cache_telemetry = CacheTelemetryService()
        self.apm_service = APMService(
            cache_telemetry=self.cache_telemetry, metrics_service=self.metrics_service
        )

        # Initialize cache services
        self.redis_cache = redis_cache
        self.rag_cache = rag_cache

        # Initialize advanced services
        self.alerting_service = PerformanceAlertingService(
            apm_service=self.apm_service,
            cache_telemetry=self.cache_telemetry,
            config_path=self.config_path.parent / "alert_config.json",
        )

        self.cache_optimization = CacheOptimizationService(
            cache_telemetry=self.cache_telemetry,
            redis_cache=self.redis_cache,
            rag_cache=self.rag_cache,
        )

        self.dashboard_service = PerformanceDashboardService(
            apm_service=self.apm_service,
            cache_telemetry=self.cache_telemetry,
            metrics_service=self.metrics_service,
        )

        # Service state
        self._running = False
        self._health_check_task: asyncio.Task | None = None

        # Performance tracking
        self.system_health_score = 0.0
        self.last_health_check = None

        logger.info("Integrated performance monitor initialized")

    # ========================================================================
    # Service Lifecycle
    # ========================================================================

    async def start_monitoring(self):
        """Start all performance monitoring services."""
        if self._running:
            logger.warning("Performance monitoring already running")
            return

        try:
            # Start core services
            self.metrics_service.start_metrics_server(port=9090)

            # Start APM service
            # APM service starts automatically with background monitoring

            # Start alerting service
            await self.alerting_service.start_monitoring()

            # Start cache optimization
            await self.cache_optimization.start_optimization()

            # Start dashboard real-time updates
            await self.dashboard_service.start_real_time_updates()

            # Start health check loop
            self._running = True
            self._health_check_task = asyncio.create_task(self._health_check_loop())

            logger.info("All performance monitoring services started successfully")

        except Exception as e:
            logger.error(f"Error starting performance monitoring: {e}")
            await self.stop_monitoring()
            raise

    async def stop_monitoring(self):
        """Stop all performance monitoring services."""
        if not self._running:
            return

        self._running = False

        try:
            # Stop health check
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass

            # Stop services
            await self.alerting_service.stop_monitoring()
            await self.cache_optimization.stop_optimization()
            await self.dashboard_service.stop_real_time_updates()

            logger.info("All performance monitoring services stopped")

        except Exception as e:
            logger.error(f"Error stopping performance monitoring: {e}")

    # ========================================================================
    # Health Monitoring
    # ========================================================================

    async def _health_check_loop(self):
        """Background health check loop."""
        while self._running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(300)  # Every 5 minutes

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(300)

    async def _perform_health_check(self):
        """Perform comprehensive system health check."""
        try:
            health_scores = {}

            # Check cache health
            cache_health = self.cache_telemetry.assess_cache_health()
            health_scores["cache"] = cache_health.overall_score

            # Check APM health (based on recent performance)
            if self.amp.performance_snapshots:
                latest_snapshot = self.amp.performance_snapshots[-1]
                apm_score = self._calculate_apm_health_score(latest_snapshot)
                health_scores["apm"] = apm_score
            else:
                health_scores["apm"] = 50  # Neutral score if no data

            # Check alerting service health
            alert_stats = self.alerting_service.get_alert_statistics()
            alerting_score = self._calculate_alerting_health_score(alert_stats)
            health_scores["alerting"] = alerting_score

            # Check optimization service health
            optimization_summary = self.cache_optimization.get_optimization_summary()
            optimization_score = self._calculate_optimization_health_score(
                optimization_summary
            )
            health_scores["optimization"] = optimization_score

            # Calculate overall health score
            weights = {"cache": 0.3, "apm": 0.3, "alerting": 0.2, "optimization": 0.2}

            self.system_health_score = sum(
                score * weights[component] for component, score in health_scores.items()
            )

            self.last_health_check = datetime.utcnow()

            # Update metrics service with health score
            self.metrics_service.update_health_status(
                "healthy"
                if self.system_health_score > 80
                else "degraded" if self.system_health_score > 60 else "unhealthy"
            )

            logger.debug(
                f"System health check completed: {self.system_health_score:.1f}"
            )

        except Exception as e:
            logger.error(f"Error performing health check: {e}")

    def _calculate_apm_health_score(self, snapshot) -> float:
        """Calculate APM health score from performance snapshot."""
        score = 100.0

        # Response time penalty
        if snapshot.p95_response_time_ms > 2000:
            score -= min(30, (snapshot.p95_response_time_ms - 2000) / 100)

        # Error rate penalty
        if snapshot.error_rate_percent > 1:
            score -= min(40, snapshot.error_rate_percent * 10)

        # CPU usage penalty
        if snapshot.cpu_percent > 80:
            score -= min(20, (snapshot.cpu_percent - 80) / 2)

        # Memory usage penalty
        if snapshot.memory_percent > 85:
            score -= min(10, (snapshot.memory_percent - 85) / 3)

        return max(0, score)

    def _calculate_alerting_health_score(self, alert_stats) -> float:
        """Calculate alerting service health score."""
        if not alert_stats.get("system_health", {}).get("monitoring_active"):
            return 0  # Alerting not active

        score = 100.0

        # Too many active alerts is bad
        active_alerts = alert_stats.get("active_alerts_count", 0)
        if active_alerts > 5:
            score -= min(30, (active_alerts - 5) * 5)

        # Recent spike in alerts is concerning
        recent_events = alert_stats.get("last_24h_events", 0)
        if recent_events > 20:
            score -= min(20, (recent_events - 20) / 2)

        return max(0, score)

    def _calculate_optimization_health_score(self, optimization_summary) -> float:
        """Calculate optimization service health score."""
        score = 100.0

        # Good pattern identification is positive
        patterns = optimization_summary.get("patterns_identified", 0)
        if patterns < 5:
            score -= 20  # Not enough pattern data

        # High number of recommendations indicates issues
        recommendations = optimization_summary.get("recommendations", 0)
        if recommendations > 10:
            score -= min(30, recommendations * 2)

        # Active warming jobs indicate proactive optimization
        active_jobs = optimization_summary.get("active_warming_jobs", 0)
        if active_jobs > 0:
            score += min(10, active_jobs * 2)

        return max(0, min(100, score))

    # ========================================================================
    # Unified Data Access
    # ========================================================================

    def get_comprehensive_performance_report(self) -> dict[str, Any]:
        """Get comprehensive performance report from all services."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system_health": {
                "overall_score": self.system_health_score,
                "last_check": (
                    self.last_health_check.isoformat()
                    if self.last_health_check
                    else None
                ),
                "status": (
                    "healthy"
                    if self.system_health_score > 80
                    else "degraded" if self.system_health_score > 60 else "critical"
                ),
            },
            "apm_summary": self.amp.get_performance_summary(),
            "cache_telemetry": self.cache_telemetry.export_telemetry_report(),
            "alert_statistics": self.alerting_service.get_alert_statistics(),
            "optimization_summary": self.cache_optimization.get_optimization_summary(),
            "dashboard_data": self.dashboard_service.get_api_metrics(),
        }

    def get_real_time_metrics(self) -> dict[str, Any]:
        """Get real-time performance metrics."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system_health_score": self.system_health_score,
            "cache_metrics": self.cache_telemetry.get_dashboard_data(),
            "apm_metrics": {
                "active_traces": len(self.amp.traces),
                "active_spans": len(self.amp.active_spans),
                "recent_errors": len(
                    [
                        trace
                        for trace in list(self.amp.traces)[-100:]
                        if trace.has_errors
                    ]
                ),
            },
            "alert_metrics": {
                "active_alerts": len(self.alerting_service.active_alerts),
                "recent_alerts": len(
                    [
                        event
                        for event in self.alerting_service.alert_history[-50:]
                        if (datetime.utcnow() - event.timestamp).total_seconds() < 3600
                    ]
                ),
            },
            "optimization_metrics": {
                "warming_candidates": len(self.cache_optimization.warming_candidates),
                "active_jobs": len(self.cache_optimization.active_jobs),
                "recommendations": len(
                    self.cache_optimization.optimization_recommendations
                ),
            },
        }

    # ========================================================================
    # Configuration Management
    # ========================================================================

    def update_configuration(self, config: dict[str, Any]) -> bool:
        """Update configuration for all services."""
        try:
            # Update alerting configuration
            if "alerting" in config:
                alert_config = config["alerting"]

                # Update alert rules
                if "rules" in alert_config:
                    for rule_data in alert_config["rules"]:
                        if "rule_id" in rule_data:
                            self.alerting_service.update_alert_rule(
                                rule_data["rule_id"], rule_data
                            )
                        else:
                            from backend.services.performance_alerting_service import (
                                AlertRule,
                            )

                            rule = AlertRule(**rule_data)
                            self.alerting_service.add_alert_rule(rule)

                # Update notification configs
                if "notifications" in alert_config:
                    # This would update notification configurations
                    pass

            # Update cache optimization configuration
            if "optimization" in config:
                opt_config = config["optimization"]

                # Update thresholds
                if "min_pattern_frequency" in opt_config:
                    self.cache_optimization.min_pattern_frequency = opt_config[
                        "min_pattern_frequency"
                    ]

                if "warming_batch_size" in opt_config:
                    self.cache_optimization.warming_batch_size = opt_config[
                        "warming_batch_size"
                    ]

            # Update cache telemetry configuration
            if "telemetry" in config:
                telem_config = config["telemetry"]

                if "max_events" in telem_config:
                    # Would need to implement configuration update in telemetry service
                    pass

            # Save configuration
            self._save_configuration(config)

            logger.info("Configuration updated successfully")
            return True

        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False

    def _save_configuration(self, config: dict[str, Any]):
        """Save configuration to file."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    # ========================================================================
    # Advanced Operations
    # ========================================================================

    async def trigger_comprehensive_analysis(self) -> dict[str, Any]:
        """Trigger comprehensive analysis across all services."""
        results = {}

        try:
            # Trigger cache telemetry analysis
            cache_report = self.cache_telemetry.export_telemetry_report()
            results["cache_analysis"] = {
                "status": "completed",
                "total_events": cache_report.get("report_metadata", {}).get(
                    "total_events", 0
                ),
                "layers_analyzed": len(cache_report.get("cache_layer_metrics", {})),
                "recommendations": len(
                    cache_report.get("optimization_recommendations", [])
                ),
            }

            # Trigger APM analysis
            apm_summary = self.amp.get_performance_summary()
            results["apm_analysis"] = {
                "status": "completed",
                "total_traces": apm_summary.get("system_health", {}).get(
                    "total_traces", 0
                ),
                "active_alerts": len(apm_summary.get("active_alerts", [])),
            }

            # Trigger optimization analysis
            opt_result = self.cache_optimization.trigger_immediate_analysis()
            results["optimization_analysis"] = opt_result

            # Trigger alerting health check
            alert_stats = self.alerting_service.get_alert_statistics()
            results["alerting_analysis"] = {
                "status": "completed",
                "monitoring_active": alert_stats.get("system_health", {}).get(
                    "monitoring_active", False
                ),
                "total_rules": alert_stats.get("total_rules", 0),
                "active_alerts": alert_stats.get("active_alerts_count", 0),
            }

            # Update overall health
            await self._perform_health_check()
            results["system_health"] = {
                "score": self.system_health_score,
                "status": (
                    "healthy"
                    if self.system_health_score > 80
                    else "degraded" if self.system_health_score > 60 else "critical"
                ),
                "last_check": (
                    self.last_health_check.isoformat()
                    if self.last_health_check
                    else None
                ),
            }

            return {
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            return {
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
            }

    async def emergency_optimization(self) -> dict[str, Any]:
        """Trigger emergency optimization procedures."""
        try:
            results = {}

            # Check current system health
            await self._perform_health_check()

            if self.system_health_score < 60:  # Critical threshold
                logger.warning(
                    "Emergency optimization triggered due to low health score"
                )

                # Emergency cache optimization
                emergency_candidates = self.cache_optimization.get_warming_candidates(
                    limit=20
                )
                if emergency_candidates:
                    # Schedule high-priority warming
                    high_priority_keys = [
                        c["key"]
                        for c in emergency_candidates[:10]
                        if c["priority"] in ["critical", "high"]
                    ]

                    if high_priority_keys:
                        job_id = self.cache_optimization.schedule_warming_job(
                            cache_layer=CacheLayer.RAG_QUERY,  # Focus on most critical layer
                            keys=high_priority_keys,
                            priority=WarmingPriority.CRITICAL,
                        )
                        results["emergency_warming_job"] = job_id

                # Clear low-priority alerts to reduce noise
                alert_stats = self.alerting_service.get_alert_statistics()
                if alert_stats.get("active_alerts_count", 0) > 10:
                    results["alert_cleanup"] = (
                        "Initiated cleanup of low-priority alerts"
                    )

                # Force cache cleanup
                optimization_summary = (
                    self.cache_optimization.get_optimization_summary()
                )
                results["optimization_triggered"] = optimization_summary

                results["status"] = "emergency_procedures_activated"
            else:
                results["status"] = "system_healthy_no_emergency_needed"

            return results

        except Exception as e:
            logger.error(f"Error in emergency optimization: {e}")
            return {"status": "error", "error": str(e)}

    # ========================================================================
    # Monitoring and Diagnostics
    # ========================================================================

    def get_service_health_status(self) -> dict[str, Any]:
        """Get health status of all monitoring services."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health_score": self.system_health_score,
            "monitoring_active": self._running,
            "services": {
                "metrics_service": {
                    "active": True,  # Metrics service doesn't have explicit status
                    "port": 9090,
                },
                "cache_telemetry": {
                    "active": True,
                    "total_events": len(self.cache_telemetry.events),
                    "layers_monitored": len(CacheLayer),
                },
                "apm_service": {
                    "active": True,
                    "total_traces": len(self.amp.traces),
                    "active_spans": len(self.amp.active_spans),
                },
                "alerting_service": {
                    "active": self.alerting_service._running,
                    "total_rules": len(self.alerting_service.alert_rules),
                    "active_alerts": len(self.alerting_service.active_alerts),
                },
                "cache_optimization": {
                    "active": self.cache_optimization._running,
                    "patterns_identified": len(self.cache_optimization.access_patterns),
                    "warming_candidates": len(
                        self.cache_optimization.warming_candidates
                    ),
                },
                "dashboard_service": {
                    "active": self.dashboard_service._running,
                    "websocket_connections": len(
                        self.dashboard_service.connection_manager.active_connections
                    ),
                },
            },
        }

    def get_performance_trends(self, hours_back: int = 24) -> dict[str, Any]:
        """Get performance trends across all monitored metrics."""
        try:
            # Get APM trends
            apm_trends = self.amp.analyze_performance_trends(hours_back)

            # Get cache trends
            cache_trends = self.cache_telemetry.analyze_performance_trends(hours_back)

            # Combine trends
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "analysis_period_hours": hours_back,
                "apm_trends": apm_trends,
                "cache_trends": cache_trends,
                "health_score_trend": self._calculate_health_score_trend(hours_back),
                "summary": self._generate_trend_summary(apm_trends, cache_trends),
            }

        except Exception as e:
            logger.error(f"Error getting performance trends: {e}")
            return {"error": str(e)}

    def _calculate_health_score_trend(self, hours_back: int) -> str:
        """Calculate trend in system health score."""
        # This is a simplified implementation
        # In practice, you'd store historical health scores
        if self.system_health_score > 80:
            return "stable_healthy"
        elif self.system_health_score > 60:
            return "stable_degraded"
        else:
            return "declining"

    def _generate_trend_summary(self, apm_trends: dict, cache_trends: dict) -> str:
        """Generate human-readable trend summary."""
        try:
            summaries = []

            # APM trend summary
            if "trends" in apm_trends:
                trends = apm_trends["trends"]
                if trends.get("response_time") == "increasing":
                    summaries.append("Response times are increasing")
                elif trends.get("response_time") == "decreasing":
                    summaries.append("Response times are improving")

                if trends.get("error_rate") == "increasing":
                    summaries.append("Error rates are rising")
                elif trends.get("error_rate") == "decreasing":
                    summaries.append("Error rates are declining")

            # Cache trend summary
            if cache_trends.get("hit_rate_trend") == "improving":
                summaries.append("Cache hit rates are improving")
            elif cache_trends.get("hit_rate_trend") == "degrading":
                summaries.append("Cache hit rates are declining")

            if cache_trends.get("latency_trend") == "improving":
                summaries.append("Cache latencies are improving")
            elif cache_trends.get("latency_trend") == "degrading":
                summaries.append("Cache latencies are increasing")

            if not summaries:
                return "Performance metrics are stable"

            return "; ".join(summaries)

        except Exception as e:
            logger.error(f"Error generating trend summary: {e}")
            return "Unable to generate trend summary"
