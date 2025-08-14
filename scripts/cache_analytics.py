#!/usr/bin/env python3
"""
Cache Performance Analytics
Advanced analytics and reporting for cache performance optimization.
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.redis_cache_service import RedisCacheService
from backend.services.smart_cache_manager import SmartCacheManager
from backend.services.cache_warming_service import CacheWarmingService
from backend.services.redis_monitoring import RedisMonitoringService

logger = logging.getLogger(__name__)


# ============================================================================
# Analytics Data Classes
# ============================================================================

@dataclass
class CacheAnalyticsMetrics:
    """Comprehensive cache analytics metrics."""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Hit/Miss Statistics
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    hit_rate_percent: float = 0.0

    # Performance Metrics
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    cache_hit_response_time_ms: float = 0.0
    cache_miss_response_time_ms: float = 0.0

    # Memory and Size Metrics
    total_cached_size_mb: float = 0.0
    avg_item_size_kb: float = 0.0
    memory_utilization_percent: float = 0.0
    eviction_count: int = 0

    # Key Pattern Analysis
    top_accessed_patterns: Dict[str, int] = field(default_factory=dict)
    key_distribution: Dict[str, int] = field(default_factory=dict)

    # Time-based Analysis
    hourly_hit_rates: Dict[int, float] = field(default_factory=dict)
    daily_patterns: Dict[str, float] = field(default_factory=dict)

    # Strategy Effectiveness
    strategy_performance: Dict[str, float] = field(default_factory=dict)
    warming_effectiveness: float = 0.0

    # Cost Analysis
    estimated_cost_savings_usd: float = 0.0
    database_load_reduction_percent: float = 0.0


@dataclass
class CacheRecommendation:
    """Cache optimization recommendation."""
    category: str  # performance, memory, strategy, configuration
    priority: str  # critical, high, medium, low
    title: str
    description: str
    impact: str  # high, medium, low
    effort: str  # high, medium, low
    current_value: Any = None
    recommended_value: Any = None
    estimated_improvement: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# ============================================================================
# Cache Analytics Engine
# ============================================================================

class CacheAnalyticsEngine:
    """
    Advanced cache analytics and performance analysis engine.
    """

    def __init__(
        self,
        redis_cache: Optional[RedisCacheService] = None,
        smart_cache: Optional[SmartCacheManager] = None,
        warming_service: Optional[CacheWarmingService] = None,
        monitoring_service: Optional[RedisMonitoringService] = None
    ):
        """Initialize cache analytics engine."""
        self.redis_cache = redis_cache
        self.smart_cache = smart_cache
        self.warming_service = warming_service
        self.monitoring_service = monitoring_service

        # Historical data storage
        self.historical_metrics: deque = deque(maxlen=10000)
        self.key_access_history: Dict[str, List[Tuple[datetime, bool]]] = defaultdict(list)
        self.response_times: deque = deque(maxlen=5000)

        # Analysis configuration
        self.analysis_window_hours = 24
        self.reporting_interval_minutes = 15

        # Cost modeling parameters
        self.cpu_cost_per_hour = 0.05  # USD per CPU hour
        self.memory_cost_per_gb_hour = 0.01  # USD per GB hour
        self.db_query_cost = 0.001  # USD per database query

        logger.info("Cache Analytics Engine initialized")

    # ========================================================================
    # Data Collection
    # ========================================================================

    async def collect_current_metrics(self) -> CacheAnalyticsMetrics:
        """Collect current cache metrics from all sources."""
        metrics = CacheAnalyticsMetrics()

        try:
            # Collect from Redis cache service
            if self.redis_cache:
                redis_stats = self.redis_cache.get_stats()
                metrics.total_requests = redis_stats.get("hits", 0) + redis_stats.get("misses", 0)
                metrics.cache_hits = redis_stats.get("hits", 0)
                metrics.cache_misses = redis_stats.get("misses", 0)

                if metrics.total_requests > 0:
                    metrics.hit_rate_percent = (metrics.cache_hits / metrics.total_requests) * 100

            # Collect from smart cache manager
            if self.smart_cache:
                performance_report = self.smart_cache.get_performance_report()
                cache_metrics = performance_report.get("cache_metrics", {})

                if "hit_rate_percent" in cache_metrics:
                    metrics.hit_rate_percent = cache_metrics["hit_rate_percent"]

                metrics.total_cached_size_mb = len(self.smart_cache.key_profiles) * 0.001  # Estimate

                # Analyze key patterns
                metrics.key_distribution = self._analyze_key_patterns()
                metrics.top_accessed_patterns = self._get_top_patterns()

            # Collect from warming service
            if self.warming_service:
                warming_status = self.warming_service.get_warming_status()
                warming_stats = warming_status.get("statistics", {})

                if warming_stats.get("total_tasks", 0) > 0:
                    metrics.warming_effectiveness = (
                        warming_stats.get("completed_tasks", 0) /
                        warming_stats.get("total_tasks", 1) * 100
                    )

                metrics.strategy_performance = warming_status.get("strategy_performance", {})

            # Collect from monitoring service
            if self.monitoring_service:
                performance_summary = self.monitoring_service.get_performance_summary()
                metrics.memory_utilization_percent = (
                    performance_summary.get("total_memory_mb", 0) / 1000 * 100  # Assuming 1GB limit
                )
                metrics.avg_response_time_ms = 50.0  # Would be calculated from monitoring data

            # Calculate derived metrics
            await self._calculate_derived_metrics(metrics)

        except Exception as e:
            logger.error(f"Error collecting cache metrics: {e}")

        return metrics

    async def _calculate_derived_metrics(self, metrics: CacheAnalyticsMetrics):
        """Calculate derived metrics from collected data."""
        # Time-based analysis
        metrics.hourly_hit_rates = self._calculate_hourly_hit_rates()
        metrics.daily_patterns = self._calculate_daily_patterns()

        # Cost analysis
        metrics.estimated_cost_savings_usd = self._calculate_cost_savings(metrics)
        metrics.database_load_reduction_percent = self._calculate_db_load_reduction(metrics)

        # Performance percentiles
        if self.response_times:
            times = list(self.response_times)
            metrics.p95_response_time_ms = np.percentile(times, 95)
            metrics.p99_response_time_ms = np.percentile(times, 99)
            metrics.avg_response_time_ms = np.mean(times)

    def _analyze_key_patterns(self) -> Dict[str, int]:
        """Analyze cache key patterns."""
        patterns = defaultdict(int)

        if not self.smart_cache:
            return dict(patterns)

        for key in self.smart_cache.key_profiles.keys():
            # Extract pattern from key
            if ":" in key:
                pattern = key.split(":")[0] + ":*"
            elif "_" in key:
                pattern = key.split("_")[0] + "_*"
            else:
                pattern = "single_keys"

            patterns[pattern] += 1

        return dict(patterns)

    def _get_top_patterns(self) -> Dict[str, int]:
        """Get top accessed key patterns."""
        pattern_access = defaultdict(int)

        if not self.smart_cache:
            return dict(pattern_access)

        for key, profile in self.smart_cache.key_profiles.items():
            # Extract pattern
            if ":" in key:
                pattern = key.split(":")[0] + ":*"
            elif "_" in key:
                pattern = key.split("_")[0] + "_*"
            else:
                pattern = "single_keys"

            pattern_access[pattern] += profile.access_count

        # Return top 10 patterns
        sorted_patterns = sorted(pattern_access.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_patterns[:10])

    def _calculate_hourly_hit_rates(self) -> Dict[int, float]:
        """Calculate hit rates by hour of day."""
        hourly_data = defaultdict(lambda: {"hits": 0, "total": 0})

        # Analyze historical access data
        for key, accesses in self.key_access_history.items():
            for timestamp, hit in accesses:
                hour = timestamp.hour
                hourly_data[hour]["total"] += 1
                if hit:
                    hourly_data[hour]["hits"] += 1

        # Calculate hit rates
        hit_rates = {}
        for hour, data in hourly_data.items():
            if data["total"] > 0:
                hit_rates[hour] = (data["hits"] / data["total"]) * 100
            else:
                hit_rates[hour] = 0.0

        return hit_rates

    def _calculate_daily_patterns(self) -> Dict[str, float]:
        """Calculate daily access patterns."""
        daily_data = defaultdict(lambda: {"hits": 0, "total": 0})

        for key, accesses in self.key_access_history.items():
            for timestamp, hit in accesses:
                day = timestamp.strftime("%A")  # Day name
                daily_data[day]["total"] += 1
                if hit:
                    daily_data[day]["hits"] += 1

        # Calculate hit rates by day
        patterns = {}
        for day, data in daily_data.items():
            if data["total"] > 0:
                patterns[day] = (data["hits"] / data["total"]) * 100
            else:
                patterns[day] = 0.0

        return patterns

    def _calculate_cost_savings(self, metrics: CacheAnalyticsMetrics) -> float:
        """Calculate estimated cost savings from caching."""
        # Simplified cost calculation
        if metrics.total_requests == 0:
            return 0.0

        # Assume each cache hit saves a database query
        saved_queries = metrics.cache_hits
        query_cost_savings = saved_queries * self.db_query_cost

        # CPU savings from not processing requests
        estimated_cpu_savings_hours = (metrics.cache_hits * 0.001)  # 1ms CPU per hit saved
        cpu_cost_savings = estimated_cpu_savings_hours * self.cpu_cost_per_hour

        return query_cost_savings + cpu_cost_savings

    def _calculate_db_load_reduction(self, metrics: CacheAnalyticsMetrics) -> float:
        """Calculate database load reduction percentage."""
        if metrics.total_requests == 0:
            return 0.0

        # Assume each cache hit eliminates a database query
        return (metrics.cache_hits / metrics.total_requests) * 100

    # ========================================================================
    # Analysis and Recommendations
    # ========================================================================

    async def analyze_performance(self) -> List[CacheRecommendation]:
        """Analyze cache performance and generate recommendations."""
        recommendations = []

        # Collect current metrics
        metrics = await self.collect_current_metrics()

        # Hit rate analysis
        if metrics.hit_rate_percent < 50:
            recommendations.append(CacheRecommendation(
                category="performance",
                priority="critical",
                title="Low Cache Hit Rate",
                description=f"Cache hit rate is {metrics.hit_rate_percent:.1f}%, which is below optimal levels.",
                impact="high",
                effort="medium",
                current_value=f"{metrics.hit_rate_percent:.1f}%",
                recommended_value="80%+",
                estimated_improvement="Reduce database load by 30-50%"
            ))
        elif metrics.hit_rate_percent < 80:
            recommendations.append(CacheRecommendation(
                category="performance",
                priority="high",
                title="Suboptimal Cache Hit Rate",
                description=f"Cache hit rate is {metrics.hit_rate_percent:.1f}%. There's room for improvement.",
                impact="medium",
                effort="low",
                current_value=f"{metrics.hit_rate_percent:.1f}%",
                recommended_value="80%+",
                estimated_improvement="Reduce database load by 10-20%"
            ))

        # Memory utilization analysis
        if metrics.memory_utilization_percent > 90:
            recommendations.append(CacheRecommendation(
                category="memory",
                priority="critical",
                title="High Memory Utilization",
                description=f"Memory utilization is {metrics.memory_utilization_percent:.1f}%, approaching limits.",
                impact="high",
                effort="medium",
                current_value=f"{metrics.memory_utilization_percent:.1f}%",
                recommended_value="<80%",
                estimated_improvement="Prevent cache evictions and performance degradation"
            ))

        # Response time analysis
        if metrics.avg_response_time_ms > 100:
            recommendations.append(CacheRecommendation(
                category="performance",
                priority="high",
                title="High Response Time",
                description=f"Average response time is {metrics.avg_response_time_ms:.1f}ms, above optimal levels.",
                impact="medium",
                effort="medium",
                current_value=f"{metrics.avg_response_time_ms:.1f}ms",
                recommended_value="<50ms",
                estimated_improvement="Improve user experience and throughput"
            ))

        # Warming effectiveness analysis
        if metrics.warming_effectiveness < 80:
            recommendations.append(CacheRecommendation(
                category="strategy",
                priority="medium",
                title="Low Cache Warming Effectiveness",
                description=f"Cache warming success rate is {metrics.warming_effectiveness:.1f}%.",
                impact="medium",
                effort="low",
                current_value=f"{metrics.warming_effectiveness:.1f}%",
                recommended_value="90%+",
                estimated_improvement="Proactive cache population for better hit rates"
            ))

        # Key pattern analysis
        await self._analyze_key_patterns_for_recommendations(recommendations, metrics)

        # Time-based pattern analysis
        await self._analyze_temporal_patterns_for_recommendations(recommendations, metrics)

        return recommendations

    async def _analyze_key_patterns_for_recommendations(
        self,
        recommendations: List[CacheRecommendation],
        metrics: CacheAnalyticsMetrics
    ):
        """Analyze key patterns and add relevant recommendations."""
        if not metrics.key_distribution:
            return

        # Check for pattern concentration
        total_keys = sum(metrics.key_distribution.values())
        largest_pattern = max(metrics.key_distribution.values())
        concentration_ratio = largest_pattern / total_keys if total_keys > 0 else 0

        if concentration_ratio > 0.7:
            recommendations.append(CacheRecommendation(
                category="strategy",
                priority="medium",
                title="High Key Pattern Concentration",
                description=f"70%+ of keys follow a single pattern. Consider pattern-specific optimization.",
                impact="medium",
                effort="medium",
                current_value=f"{concentration_ratio:.1%} concentration",
                recommended_value="Diversified patterns",
                estimated_improvement="Better resource utilization and cache distribution"
            ))

        # Check for too many small patterns
        small_patterns = sum(1 for count in metrics.key_distribution.values() if count < 5)
        if small_patterns > len(metrics.key_distribution) * 0.5:
            recommendations.append(CacheRecommendation(
                category="configuration",
                priority="low",
                title="Key Pattern Fragmentation",
                description="Many key patterns have very few keys. Consider consolidation.",
                impact="low",
                effort="high",
                current_value=f"{small_patterns} small patterns",
                recommended_value="Consolidated patterns",
                estimated_improvement="Simplified management and better cache locality"
            ))

    async def _analyze_temporal_patterns_for_recommendations(
        self,
        recommendations: List[CacheRecommendation],
        metrics: CacheAnalyticsMetrics
    ):
        """Analyze temporal access patterns for recommendations."""
        if not metrics.hourly_hit_rates:
            return

        # Check for significant hourly variations
        hit_rates = list(metrics.hourly_hit_rates.values())
        if len(hit_rates) > 1:
            hit_rate_std = np.std(hit_rates)
            hit_rate_mean = np.mean(hit_rates)

            if hit_rate_std > hit_rate_mean * 0.3:  # High variation
                recommendations.append(CacheRecommendation(
                    category="strategy",
                    priority="medium",
                    title="High Temporal Hit Rate Variation",
                    description="Cache hit rates vary significantly by time of day.",
                    impact="medium",
                    effort="medium",
                    current_value=f"±{hit_rate_std:.1f}% variation",
                    recommended_value="Consistent performance",
                    estimated_improvement="Time-based cache warming and TTL optimization"
                ))

    # ========================================================================
    # Reporting and Visualization
    # ========================================================================

    async def generate_comprehensive_report(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Generate comprehensive cache analytics report."""
        # Collect current metrics
        current_metrics = await self.collect_current_metrics()

        # Generate recommendations
        recommendations = await self.analyze_performance()

        # Create report
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "analysis_period_hours": self.analysis_window_hours,
            "executive_summary": self._generate_executive_summary(current_metrics, recommendations),
            "current_metrics": asdict(current_metrics),
            "recommendations": [rec.to_dict() for rec in recommendations],
            "detailed_analysis": {
                "performance_trends": await self._analyze_performance_trends(),
                "key_analysis": await self._analyze_key_distribution(),
                "temporal_analysis": await self._analyze_temporal_patterns(),
                "cost_analysis": await self._analyze_cost_impact(current_metrics)
            },
            "configuration_review": await self._review_configuration(),
            "next_steps": self._generate_next_steps(recommendations)
        }

        # Save to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Cache analytics report saved to {output_file}")

        return report

    def _generate_executive_summary(
        self,
        metrics: CacheAnalyticsMetrics,
        recommendations: List[CacheRecommendation]
    ) -> Dict[str, Any]:
        """Generate executive summary."""
        # Categorize recommendations by priority
        critical_recs = [r for r in recommendations if r.priority == "critical"]
        high_recs = [r for r in recommendations if r.priority == "high"]

        # Overall health score (0-100)
        health_score = 100
        if metrics.hit_rate_percent < 80:
            health_score -= (80 - metrics.hit_rate_percent)
        if metrics.memory_utilization_percent > 80:
            health_score -= (metrics.memory_utilization_percent - 80)
        if metrics.avg_response_time_ms > 50:
            health_score -= min(50, metrics.avg_response_time_ms - 50)

        health_score = max(0, health_score)

        return {
            "overall_health_score": round(health_score),
            "cache_hit_rate": f"{metrics.hit_rate_percent:.1f}%",
            "estimated_monthly_savings": f"${metrics.estimated_cost_savings_usd * 30:.2f}",
            "database_load_reduction": f"{metrics.database_load_reduction_percent:.1f}%",
            "critical_issues": len(critical_recs),
            "high_priority_issues": len(high_recs),
            "key_findings": [
                f"Cache hit rate: {metrics.hit_rate_percent:.1f}%",
                f"Memory utilization: {metrics.memory_utilization_percent:.1f}%",
                f"Average response time: {metrics.avg_response_time_ms:.1f}ms",
                f"Active key patterns: {len(metrics.key_distribution)}"
            ]
        }

    async def _analyze_performance_trends(self) -> Dict[str, Any]:
        """Analyze performance trends over time."""
        if len(self.historical_metrics) < 2:
            return {"message": "Insufficient historical data for trend analysis"}

        # Convert to pandas DataFrame for analysis
        df_data = []
        for metric in self.historical_metrics:
            df_data.append({
                "timestamp": metric.timestamp,
                "hit_rate": metric.hit_rate_percent,
                "response_time": metric.avg_response_time_ms,
                "memory_utilization": metric.memory_utilization_percent
            })

        df = pd.DataFrame(df_data)

        # Calculate trends
        trends = {}
        for column in ["hit_rate", "response_time", "memory_utilization"]:
            if len(df) > 1:
                slope, intercept, r_value, p_value, std_err = stats.linregress(
                    range(len(df)), df[column]
                )
                trends[column] = {
                    "slope": slope,
                    "trend": "improving" if slope < 0 and column == "response_time" else "improving" if slope > 0 and column != "response_time" else "declining" if slope != 0 else "stable",
                    "r_squared": r_value ** 2
                }

        return trends

    async def _analyze_key_distribution(self) -> Dict[str, Any]:
        """Analyze cache key distribution."""
        if not self.smart_cache:
            return {"message": "Smart cache not available for key analysis"}

        # Analyze key profiles
        total_keys = len(self.smart_cache.key_profiles)
        pattern_analysis = {}

        # Access pattern distribution
        pattern_counts = defaultdict(int)
        for profile in self.smart_cache.key_profiles.values():
            pattern_counts[profile.access_pattern.value] += 1

        pattern_analysis["access_patterns"] = dict(pattern_counts)

        # Key age distribution
        now = datetime.utcnow()
        age_buckets = {"< 1 hour": 0, "1-24 hours": 0, "1-7 days": 0, "> 7 days": 0}

        for profile in self.smart_cache.key_profiles.values():
            age = now - profile.first_access
            if age < timedelta(hours=1):
                age_buckets["< 1 hour"] += 1
            elif age < timedelta(hours=24):
                age_buckets["1-24 hours"] += 1
            elif age < timedelta(days=7):
                age_buckets["1-7 days"] += 1
            else:
                age_buckets["> 7 days"] += 1

        pattern_analysis["age_distribution"] = age_buckets

        return {
            "total_keys": total_keys,
            "pattern_analysis": pattern_analysis,
            "top_keys_by_access": [
                {
                    "key": profile.key,
                    "access_count": profile.access_count,
                    "hit_rate": (profile.hit_count / profile.access_count * 100) if profile.access_count > 0 else 0
                }
                for profile in sorted(
                    self.smart_cache.key_profiles.values(),
                    key=lambda p: p.access_count,
                    reverse=True
                )[:10]
            ]
        }

    async def _analyze_temporal_patterns(self) -> Dict[str, Any]:
        """Analyze temporal access patterns."""
        if not self.key_access_history:
            return {"message": "No access history available"}

        # Analyze access patterns by hour and day
        hourly_accesses = defaultdict(int)
        daily_accesses = defaultdict(int)

        for accesses in self.key_access_history.values():
            for timestamp, hit in accesses:
                hourly_accesses[timestamp.hour] += 1
                daily_accesses[timestamp.strftime("%A")] += 1

        return {
            "peak_hours": sorted(hourly_accesses.items(), key=lambda x: x[1], reverse=True)[:5],
            "peak_days": sorted(daily_accesses.items(), key=lambda x: x[1], reverse=True),
            "access_patterns": {
                "hourly_distribution": dict(hourly_accesses),
                "daily_distribution": dict(daily_accesses)
            }
        }

    async def _analyze_cost_impact(self, metrics: CacheAnalyticsMetrics) -> Dict[str, Any]:
        """Analyze cost impact of caching."""
        # Calculate various cost metrics
        daily_cost_savings = metrics.estimated_cost_savings_usd
        monthly_cost_savings = daily_cost_savings * 30
        yearly_cost_savings = daily_cost_savings * 365

        # Calculate ROI (assuming cache infrastructure costs)
        estimated_cache_infrastructure_cost_monthly = 50.0  # USD
        monthly_roi = ((monthly_cost_savings - estimated_cache_infrastructure_cost_monthly) /
                      estimated_cache_infrastructure_cost_monthly * 100) if estimated_cache_infrastructure_cost_monthly > 0 else 0

        return {
            "daily_savings": f"${daily_cost_savings:.2f}",
            "monthly_savings": f"${monthly_cost_savings:.2f}",
            "yearly_savings": f"${yearly_cost_savings:.2f}",
            "monthly_roi_percent": f"{monthly_roi:.1f}%",
            "database_queries_saved": metrics.cache_hits,
            "estimated_infrastructure_cost": f"${estimated_cache_infrastructure_cost_monthly:.2f}/month"
        }

    async def _review_configuration(self) -> Dict[str, Any]:
        """Review current cache configuration."""
        config_review = {
            "redis_configuration": {},
            "smart_cache_settings": {},
            "warming_configuration": {},
            "recommendations": []
        }

        # Review Redis configuration
        if self.redis_cache:
            redis_stats = self.redis_cache.get_stats()
            config_review["redis_configuration"] = {
                "total_operations": redis_stats.get("hits", 0) + redis_stats.get("misses", 0),
                "error_count": redis_stats.get("errors", 0),
                "connection_status": "healthy" if redis_stats.get("errors", 0) == 0 else "issues_detected"
            }

        # Review smart cache settings
        if self.smart_cache:
            performance_report = self.smart_cache.get_performance_report()
            config_review["smart_cache_settings"] = {
                "ml_model_trained": performance_report.get("cache_metrics", {}).get("ml_model_trained", False),
                "total_keys": performance_report.get("cache_metrics", {}).get("total_keys", 0),
                "access_patterns": performance_report.get("access_patterns", {})
            }

        # Review warming configuration
        if self.warming_service:
            warming_status = self.warming_service.get_warming_status()
            config_review["warming_configuration"] = {
                "workers_active": warming_status.get("active_workers", 0),
                "queue_size": warming_status.get("queue_size", 0),
                "success_rate": (
                    warming_status.get("statistics", {}).get("completed_tasks", 0) /
                    max(1, warming_status.get("statistics", {}).get("total_tasks", 1)) * 100
                )
            }

        return config_review

    def _generate_next_steps(self, recommendations: List[CacheRecommendation]) -> List[str]:
        """Generate actionable next steps."""
        next_steps = []

        # Prioritize critical and high-priority recommendations
        critical_recs = [r for r in recommendations if r.priority == "critical"]
        high_recs = [r for r in recommendations if r.priority == "high"]

        if critical_recs:
            next_steps.append("Address critical issues immediately:")
            for rec in critical_recs[:3]:  # Top 3 critical
                next_steps.append(f"  - {rec.title}: {rec.description}")

        if high_recs:
            next_steps.append("Plan high-priority improvements:")
            for rec in high_recs[:3]:  # Top 3 high-priority
                next_steps.append(f"  - {rec.title}: {rec.description}")

        # Add general recommendations
        next_steps.extend([
            "Monitor cache performance continuously",
            "Review and adjust TTL settings based on access patterns",
            "Consider implementing cache warming for predictable workloads",
            "Regular review of key patterns and cache strategies"
        ])

        return next_steps

    # ========================================================================
    # Visualization
    # ========================================================================

    async def create_performance_dashboard(self, output_dir: str = "."):
        """Create visual performance dashboard."""
        try:
            # Set style
            plt.style.use('seaborn-v0_8')
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle('Cache Performance Dashboard', fontsize=16)

            # Collect current metrics
            metrics = await self.collect_current_metrics()

            # Plot 1: Hit Rate Over Time
            if self.historical_metrics:
                timestamps = [m.timestamp for m in self.historical_metrics]
                hit_rates = [m.hit_rate_percent for m in self.historical_metrics]

                axes[0, 0].plot(timestamps, hit_rates, marker='o')
                axes[0, 0].set_title('Cache Hit Rate Trend')
                axes[0, 0].set_ylabel('Hit Rate (%)')
                axes[0, 0].tick_params(axis='x', rotation=45)

            # Plot 2: Response Time Distribution
            if self.response_times:
                axes[0, 1].hist(list(self.response_times), bins=30, alpha=0.7)
                axes[0, 1].set_title('Response Time Distribution')
                axes[0, 1].set_xlabel('Response Time (ms)')
                axes[0, 1].set_ylabel('Frequency')

            # Plot 3: Key Pattern Distribution
            if metrics.key_distribution:
                patterns = list(metrics.key_distribution.keys())
                counts = list(metrics.key_distribution.values())

                axes[1, 0].bar(patterns, counts)
                axes[1, 0].set_title('Key Pattern Distribution')
                axes[1, 0].set_xlabel('Pattern')
                axes[1, 0].set_ylabel('Count')
                axes[1, 0].tick_params(axis='x', rotation=45)

            # Plot 4: Hourly Access Pattern
            if metrics.hourly_hit_rates:
                hours = list(metrics.hourly_hit_rates.keys())
                rates = list(metrics.hourly_hit_rates.values())

                axes[1, 1].bar(hours, rates)
                axes[1, 1].set_title('Hit Rate by Hour of Day')
                axes[1, 1].set_xlabel('Hour')
                axes[1, 1].set_ylabel('Hit Rate (%)')

            plt.tight_layout()

            # Save dashboard
            dashboard_file = os.path.join(output_dir, f"cache_dashboard_{int(time.time())}.png")
            plt.savefig(dashboard_file, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"Performance dashboard saved to {dashboard_file}")
            return dashboard_file

        except Exception as e:
            logger.error(f"Error creating performance dashboard: {e}")
            return None


# ============================================================================
# Command Line Interface
# ============================================================================

async def main():
    """Main function for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Cache Performance Analytics")
    parser.add_argument("--redis-host", default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port")
    parser.add_argument("--redis-password", help="Redis password")
    parser.add_argument("--analyze", action="store_true", help="Run performance analysis")
    parser.add_argument("--report", help="Generate comprehensive report (output file)")
    parser.add_argument("--dashboard", help="Create performance dashboard (output directory)")
    parser.add_argument("--recommendations", action="store_true", help="Generate optimization recommendations")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Create Redis cache service (if available)
        redis_cache = None
        try:
            from backend.services.redis_cache_service import RedisCacheService, RedisConfig

            redis_config = RedisConfig()
            redis_config.host = args.redis_host
            redis_config.port = args.redis_port
            redis_config.password = args.redis_password

            redis_cache = RedisCacheService(redis_config)
        except ImportError:
            logger.warning("Redis cache service not available")

        # Create analytics engine
        analytics = CacheAnalyticsEngine(redis_cache=redis_cache)

        if args.analyze:
            print("Analyzing cache performance...")
            metrics = await analytics.collect_current_metrics()
            print(f"Current hit rate: {metrics.hit_rate_percent:.1f}%")
            print(f"Total requests: {metrics.total_requests}")
            print(f"Memory utilization: {metrics.memory_utilization_percent:.1f}%")

        if args.recommendations:
            print("Generating recommendations...")
            recommendations = await analytics.analyze_performance()

            for rec in recommendations:
                priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(rec.priority, "⚪")
                print(f"{priority_icon} {rec.title}")
                print(f"   {rec.description}")
                if rec.current_value and rec.recommended_value:
                    print(f"   Current: {rec.current_value} → Recommended: {rec.recommended_value}")
                print()

        if args.report:
            print(f"Generating comprehensive report...")
            report = await analytics.generate_comprehensive_report(args.report)
            print(f"Report generated: {args.report}")

            # Print summary
            summary = report["executive_summary"]
            print(f"Health Score: {summary['overall_health_score']}/100")
            print(f"Hit Rate: {summary['cache_hit_rate']}")
            print(f"Monthly Savings: {summary['estimated_monthly_savings']}")

        if args.dashboard:
            print(f"Creating performance dashboard...")
            dashboard_file = await analytics.create_performance_dashboard(args.dashboard)
            if dashboard_file:
                print(f"Dashboard created: {dashboard_file}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))