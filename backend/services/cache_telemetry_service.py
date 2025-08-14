"""
Advanced Cache Telemetry and Performance Monitoring Service

Provides comprehensive caching telemetry, analytics, and optimization recommendations
for all cache layers in the AI Enhanced PDF Scholar system.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from statistics import mean, median, stdev

import psutil

logger = logging.getLogger(__name__)


# ============================================================================
# Cache Telemetry Data Models
# ============================================================================

class CacheLayer(str, Enum):
    """Cache layer types."""
    RAG_QUERY = "rag_query"
    VECTOR_INDEX = "vector_index"
    DATABASE = "database"
    REDIS_L2 = "redis_l2"
    HTTP_RESPONSE = "http_response"
    DOCUMENT_CONTENT = "document_content"


class CacheOperation(str, Enum):
    """Cache operation types."""
    GET = "get"
    SET = "set"
    DELETE = "delete"
    INVALIDATE = "invalidate"
    EVICT = "evict"
    EXPIRE = "expire"


class CacheStatus(str, Enum):
    """Cache operation status."""
    HIT = "hit"
    MISS = "miss"
    ERROR = "error"
    EXPIRED = "expired"
    EVICTED = "evicted"


@dataclass
class CacheEvent:
    """Individual cache operation event."""
    timestamp: datetime
    cache_layer: CacheLayer
    operation: CacheOperation
    status: CacheStatus
    key: str
    key_pattern: str
    size_bytes: int
    latency_ms: float
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheLayerMetrics:
    """Metrics for a specific cache layer."""
    layer: CacheLayer
    total_operations: int = 0
    hits: int = 0
    misses: int = 0
    errors: int = 0
    evictions: int = 0

    # Performance metrics
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # Size metrics
    total_size_mb: float = 0.0
    avg_entry_size_kb: float = 0.0
    max_entry_size_kb: float = 0.0

    # Hit rate metrics
    hit_rate_percent: float = 0.0
    miss_rate_percent: float = 0.0

    # Efficiency metrics
    throughput_ops_per_sec: float = 0.0
    memory_efficiency_percent: float = 0.0

    # TTL and expiration metrics
    avg_ttl_hours: float = 0.0
    expired_entries: int = 0

    # Key pattern analysis
    top_key_patterns: List[Dict[str, Any]] = field(default_factory=list)

    # Time-based metrics
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CacheHealthStatus:
    """Overall cache health assessment."""
    overall_score: float  # 0-100
    status: str  # healthy, degraded, critical
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    layer_scores: Dict[CacheLayer, float] = field(default_factory=dict)


@dataclass
class CacheOptimizationRecommendation:
    """Cache optimization recommendation."""
    priority: str  # high, medium, low
    category: str  # performance, memory, ttl, patterns
    description: str
    impact_estimate: str
    implementation_effort: str
    expected_improvement: Dict[str, float]


# ============================================================================
# Cache Telemetry Service
# ============================================================================

class CacheTelemetryService:
    """
    Comprehensive cache telemetry and monitoring service.
    """

    def __init__(
        self,
        max_events: int = 10000,
        analysis_window_minutes: int = 60,
        metrics_retention_hours: int = 24
    ):
        """Initialize cache telemetry service."""
        self.max_events = max_events
        self.analysis_window = timedelta(minutes=analysis_window_minutes)
        self.metrics_retention = timedelta(hours=metrics_retention_hours)

        # Event storage
        self.events: deque[CacheEvent] = deque(maxlen=max_events)
        self.layer_metrics: Dict[CacheLayer, CacheLayerMetrics] = {}

        # Real-time tracking
        self.latency_windows: Dict[CacheLayer, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.throughput_windows: Dict[CacheLayer, deque] = defaultdict(lambda: deque(maxlen=100))
        self.size_windows: Dict[CacheLayer, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Pattern analysis
        self.key_patterns: Dict[CacheLayer, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.hot_keys: Dict[CacheLayer, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Performance baselines
        self.baselines: Dict[CacheLayer, Dict[str, float]] = {}

        # Initialize metrics for all layers
        for layer in CacheLayer:
            self.layer_metrics[layer] = CacheLayerMetrics(layer=layer)

        logger.info("Cache telemetry service initialized")

    # ========================================================================
    # Event Recording
    # ========================================================================

    def record_cache_event(
        self,
        cache_layer: CacheLayer,
        operation: CacheOperation,
        status: CacheStatus,
        key: str,
        latency_ms: float,
        size_bytes: int = 0,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a cache operation event."""
        event = CacheEvent(
            timestamp=datetime.utcnow(),
            cache_layer=cache_layer,
            operation=operation,
            status=status,
            key=key,
            key_pattern=self._extract_key_pattern(key),
            size_bytes=size_bytes,
            latency_ms=latency_ms,
            ttl_seconds=ttl_seconds,
            metadata=metadata or {}
        )

        self.events.append(event)

        # Update real-time metrics
        self._update_real_time_metrics(event)

        # Update pattern tracking
        self._update_pattern_tracking(event)

    def record_cache_hit(
        self,
        cache_layer: CacheLayer,
        key: str,
        latency_ms: float,
        size_bytes: int = 0
    ) -> None:
        """Record a cache hit event."""
        self.record_cache_event(
            cache_layer=cache_layer,
            operation=CacheOperation.GET,
            status=CacheStatus.HIT,
            key=key,
            latency_ms=latency_ms,
            size_bytes=size_bytes
        )

    def record_cache_miss(
        self,
        cache_layer: CacheLayer,
        key: str,
        latency_ms: float
    ) -> None:
        """Record a cache miss event."""
        self.record_cache_event(
            cache_layer=cache_layer,
            operation=CacheOperation.GET,
            status=CacheStatus.MISS,
            key=key,
            latency_ms=latency_ms
        )

    def record_cache_set(
        self,
        cache_layer: CacheLayer,
        key: str,
        latency_ms: float,
        size_bytes: int,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """Record a cache set operation."""
        self.record_cache_event(
            cache_layer=cache_layer,
            operation=CacheOperation.SET,
            status=CacheStatus.HIT,  # Assuming successful set
            key=key,
            latency_ms=latency_ms,
            size_bytes=size_bytes,
            ttl_seconds=ttl_seconds
        )

    # ========================================================================
    # Real-time Metrics
    # ========================================================================

    def _update_real_time_metrics(self, event: CacheEvent) -> None:
        """Update real-time metric windows."""
        layer = event.cache_layer

        # Update latency window
        self.latency_windows[layer].append(event.latency_ms)

        # Update throughput window (events per second)
        current_minute = event.timestamp.minute
        if not self.throughput_windows[layer] or \
           self.throughput_windows[layer][-1][0] != current_minute:
            self.throughput_windows[layer].append((current_minute, 1))
        else:
            count = self.throughput_windows[layer][-1][1] + 1
            self.throughput_windows[layer][-1] = (current_minute, count)

        # Update size window
        if event.size_bytes > 0:
            self.size_windows[layer].append(event.size_bytes)

    def _update_pattern_tracking(self, event: CacheEvent) -> None:
        """Update key pattern and hot key tracking."""
        layer = event.cache_layer
        pattern = event.key_pattern

        # Update pattern counts
        self.key_patterns[layer][pattern] += 1

        # Track hot keys (frequently accessed)
        if event.status == CacheStatus.HIT:
            self.hot_keys[layer][event.key] += 1

    def _extract_key_pattern(self, key: str) -> str:
        """Extract generalized pattern from cache key."""
        # Replace IDs and hashes with placeholders
        import re

        # Replace numeric IDs
        pattern = re.sub(r'\d+', '{id}', key)

        # Replace hash-like strings (hex strings > 8 chars)
        pattern = re.sub(r'[a-f0-9]{8,}', '{hash}', pattern)

        # Replace UUIDs
        pattern = re.sub(
            r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',
            '{uuid}',
            pattern
        )

        return pattern

    # ========================================================================
    # Metrics Calculation
    # ========================================================================

    def calculate_layer_metrics(self, layer: CacheLayer) -> CacheLayerMetrics:
        """Calculate comprehensive metrics for a cache layer."""
        # Get recent events for this layer
        cutoff_time = datetime.utcnow() - self.analysis_window
        layer_events = [
            e for e in self.events
            if e.cache_layer == layer and e.timestamp >= cutoff_time
        ]

        if not layer_events:
            return CacheLayerMetrics(layer=layer)

        # Count operations by status
        hits = sum(1 for e in layer_events if e.status == CacheStatus.HIT)
        misses = sum(1 for e in layer_events if e.status == CacheStatus.MISS)
        errors = sum(1 for e in layer_events if e.status == CacheStatus.ERROR)
        evictions = sum(1 for e in layer_events if e.status == CacheStatus.EVICTED)
        total_operations = len(layer_events)

        # Calculate hit rates
        hit_rate = (hits / total_operations * 100) if total_operations > 0 else 0
        miss_rate = (misses / total_operations * 100) if total_operations > 0 else 0

        # Calculate latency metrics
        latencies = [e.latency_ms for e in layer_events if e.latency_ms > 0]
        avg_latency = mean(latencies) if latencies else 0
        p50_latency = median(latencies) if latencies else 0

        # Calculate percentiles
        if latencies:
            sorted_latencies = sorted(latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p99_idx = int(len(sorted_latencies) * 0.99)
            p95_latency = sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else sorted_latencies[-1]
            p99_latency = sorted_latencies[p99_idx] if p99_idx < len(sorted_latencies) else sorted_latencies[-1]
        else:
            p95_latency = p99_latency = 0

        # Calculate size metrics
        sizes = [e.size_bytes for e in layer_events if e.size_bytes > 0]
        total_size_mb = sum(sizes) / (1024 * 1024) if sizes else 0
        avg_entry_size_kb = (sum(sizes) / len(sizes) / 1024) if sizes else 0
        max_entry_size_kb = (max(sizes) / 1024) if sizes else 0

        # Calculate throughput
        time_span_seconds = self.analysis_window.total_seconds()
        throughput = total_operations / time_span_seconds if time_span_seconds > 0 else 0

        # Calculate TTL metrics
        ttl_values = [e.ttl_seconds for e in layer_events if e.ttl_seconds is not None]
        avg_ttl_hours = (mean(ttl_values) / 3600) if ttl_values else 0

        # Calculate expired entries
        expired_entries = sum(1 for e in layer_events if e.status == CacheStatus.EXPIRED)

        # Analyze key patterns
        pattern_counts = self.key_patterns[layer]
        top_patterns = [
            {"pattern": pattern, "count": count, "percentage": count / total_operations * 100}
            for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        return CacheLayerMetrics(
            layer=layer,
            total_operations=total_operations,
            hits=hits,
            misses=misses,
            errors=errors,
            evictions=evictions,
            avg_latency_ms=avg_latency,
            p50_latency_ms=p50_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            total_size_mb=total_size_mb,
            avg_entry_size_kb=avg_entry_size_kb,
            max_entry_size_kb=max_entry_size_kb,
            hit_rate_percent=hit_rate,
            miss_rate_percent=miss_rate,
            throughput_ops_per_sec=throughput,
            avg_ttl_hours=avg_ttl_hours,
            expired_entries=expired_entries,
            top_key_patterns=top_patterns,
            last_updated=datetime.utcnow()
        )

    def get_all_layer_metrics(self) -> Dict[CacheLayer, CacheLayerMetrics]:
        """Get metrics for all cache layers."""
        metrics = {}
        for layer in CacheLayer:
            metrics[layer] = self.calculate_layer_metrics(layer)
            self.layer_metrics[layer] = metrics[layer]
        return metrics

    # ========================================================================
    # Health Assessment
    # ========================================================================

    def assess_cache_health(self) -> CacheHealthStatus:
        """Assess overall cache health and performance."""
        all_metrics = self.get_all_layer_metrics()
        layer_scores = {}
        issues = []
        recommendations = []

        for layer, metrics in all_metrics.items():
            score = self._calculate_layer_health_score(metrics)
            layer_scores[layer] = score

            # Check for issues
            layer_issues, layer_recommendations = self._analyze_layer_issues(metrics)
            issues.extend(layer_issues)
            recommendations.extend(layer_recommendations)

        # Calculate overall score (weighted average)
        if layer_scores:
            # Weight more critical layers higher
            weights = {
                CacheLayer.RAG_QUERY: 0.3,
                CacheLayer.REDIS_L2: 0.25,
                CacheLayer.DATABASE: 0.2,
                CacheLayer.VECTOR_INDEX: 0.15,
                CacheLayer.DOCUMENT_CONTENT: 0.1
            }

            overall_score = sum(
                score * weights.get(layer, 0.1)
                for layer, score in layer_scores.items()
            ) / sum(weights.get(layer, 0.1) for layer in layer_scores.keys())
        else:
            overall_score = 0

        # Determine status
        if overall_score >= 80:
            status = "healthy"
        elif overall_score >= 60:
            status = "degraded"
        else:
            status = "critical"

        return CacheHealthStatus(
            overall_score=overall_score,
            status=status,
            issues=issues,
            recommendations=recommendations,
            layer_scores=layer_scores
        )

    def _calculate_layer_health_score(self, metrics: CacheLayerMetrics) -> float:
        """Calculate health score for a cache layer (0-100)."""
        score = 100.0

        # Hit rate component (0-40 points)
        if metrics.hit_rate_percent < 50:
            score -= 40 - (metrics.hit_rate_percent * 0.8)

        # Latency component (0-30 points)
        if metrics.p95_latency_ms > 100:  # Target: <100ms P95
            latency_penalty = min(30, (metrics.p95_latency_ms - 100) / 10)
            score -= latency_penalty

        # Error rate component (0-20 points)
        if metrics.total_operations > 0:
            error_rate = (metrics.errors / metrics.total_operations) * 100
            if error_rate > 1:  # Target: <1% error rate
                score -= min(20, error_rate * 2)

        # Memory efficiency component (0-10 points)
        if metrics.total_size_mb > 100:  # Threshold for memory concern
            memory_penalty = min(10, (metrics.total_size_mb - 100) / 50)
            score -= memory_penalty

        return max(0, score)

    def _analyze_layer_issues(
        self,
        metrics: CacheLayerMetrics
    ) -> Tuple[List[str], List[str]]:
        """Analyze issues and generate recommendations for a cache layer."""
        issues = []
        recommendations = []

        # Hit rate analysis
        if metrics.hit_rate_percent < 50:
            issues.append(f"{metrics.layer.value}: Low hit rate ({metrics.hit_rate_percent:.1f}%)")
            recommendations.append(f"Optimize {metrics.layer.value} cache keys and TTL settings")

        # Latency analysis
        if metrics.p95_latency_ms > 100:
            issues.append(f"{metrics.layer.value}: High P95 latency ({metrics.p95_latency_ms:.1f}ms)")
            recommendations.append(f"Investigate {metrics.layer.value} cache performance bottlenecks")

        # Memory usage analysis
        if metrics.total_size_mb > 500:
            issues.append(f"{metrics.layer.value}: High memory usage ({metrics.total_size_mb:.1f}MB)")
            recommendations.append(f"Implement more aggressive eviction for {metrics.layer.value}")

        # Error rate analysis
        if metrics.total_operations > 0:
            error_rate = (metrics.errors / metrics.total_operations) * 100
            if error_rate > 2:
                issues.append(f"{metrics.layer.value}: High error rate ({error_rate:.1f}%)")
                recommendations.append(f"Review error handling in {metrics.layer.value} cache")

        return issues, recommendations

    # ========================================================================
    # Optimization Recommendations
    # ========================================================================

    def generate_optimization_recommendations(self) -> List[CacheOptimizationRecommendation]:
        """Generate cache optimization recommendations."""
        recommendations = []
        all_metrics = self.get_all_layer_metrics()

        for layer, metrics in all_metrics.items():
            layer_recommendations = self._generate_layer_recommendations(metrics)
            recommendations.extend(layer_recommendations)

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 3))

        return recommendations

    def _generate_layer_recommendations(
        self,
        metrics: CacheLayerMetrics
    ) -> List[CacheOptimizationRecommendation]:
        """Generate optimization recommendations for a specific cache layer."""
        recommendations = []

        # Hit rate optimization
        if metrics.hit_rate_percent < 70:
            recommendations.append(CacheOptimizationRecommendation(
                priority="high",
                category="performance",
                description=f"Improve {metrics.layer.value} cache hit rate from {metrics.hit_rate_percent:.1f}%",
                impact_estimate="15-25% performance improvement",
                implementation_effort="medium",
                expected_improvement={"hit_rate": 15, "latency_reduction": 20}
            ))

        # Latency optimization
        if metrics.p95_latency_ms > 50:
            recommendations.append(CacheOptimizationRecommendation(
                priority="medium",
                category="performance",
                description=f"Reduce {metrics.layer.value} cache P95 latency from {metrics.p95_latency_ms:.1f}ms",
                impact_estimate="10-20% latency reduction",
                implementation_effort="high",
                expected_improvement={"latency_reduction": 15}
            ))

        # Memory optimization
        if metrics.avg_entry_size_kb > 100:
            recommendations.append(CacheOptimizationRecommendation(
                priority="low",
                category="memory",
                description=f"Optimize {metrics.layer.value} cache entry size (avg: {metrics.avg_entry_size_kb:.1f}KB)",
                impact_estimate="20-30% memory savings",
                implementation_effort="medium",
                expected_improvement={"memory_savings": 25}
            ))

        # TTL optimization
        if metrics.expired_entries > metrics.total_operations * 0.1:
            recommendations.append(CacheOptimizationRecommendation(
                priority="medium",
                category="ttl",
                description=f"Optimize {metrics.layer.value} TTL settings (high expiration rate)",
                impact_estimate="5-10% hit rate improvement",
                implementation_effort="low",
                expected_improvement={"hit_rate": 7, "expired_reduction": 50}
            ))

        return recommendations

    # ========================================================================
    # Predictive Cache Warming
    # ========================================================================

    def identify_cache_warming_candidates(
        self,
        layer: CacheLayer,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Identify keys that should be pre-warmed in cache."""
        # Analyze hot keys that are frequently missed
        pattern_analysis = defaultdict(lambda: {"misses": 0, "hits": 0, "keys": []})

        cutoff_time = datetime.utcnow() - timedelta(hours=1)  # Last hour
        recent_events = [
            e for e in self.events
            if e.cache_layer == layer and e.timestamp >= cutoff_time
        ]

        for event in recent_events:
            pattern = event.key_pattern
            pattern_analysis[pattern]["keys"].append(event.key)

            if event.status == CacheStatus.HIT:
                pattern_analysis[pattern]["hits"] += 1
            elif event.status == CacheStatus.MISS:
                pattern_analysis[pattern]["misses"] += 1

        # Find patterns with high miss rates but some hits (indicating value)
        warming_candidates = []
        for pattern, stats in pattern_analysis.items():
            total = stats["hits"] + stats["misses"]
            if total > 5:  # Minimum activity threshold
                miss_rate = stats["misses"] / total
                if 0.3 < miss_rate < 0.8:  # Sweet spot for warming
                    warming_candidates.append({
                        "pattern": pattern,
                        "miss_rate": miss_rate,
                        "total_requests": total,
                        "sample_keys": list(set(stats["keys"]))[:5],
                        "priority": "high" if miss_rate > 0.6 else "medium"
                    })

        # Sort by miss rate and total requests
        warming_candidates.sort(key=lambda x: (x["miss_rate"], x["total_requests"]), reverse=True)

        return warming_candidates[:limit]

    # ========================================================================
    # Performance Trending and Analysis
    # ========================================================================

    def analyze_performance_trends(
        self,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """Analyze performance trends over time."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        relevant_events = [e for e in self.events if e.timestamp >= cutoff_time]

        # Group events by hour
        hourly_stats = defaultdict(lambda: {
            "total_ops": 0,
            "hits": 0,
            "misses": 0,
            "avg_latency": 0,
            "total_latency": 0
        })

        for event in relevant_events:
            hour_key = event.timestamp.replace(minute=0, second=0, microsecond=0)
            stats = hourly_stats[hour_key]

            stats["total_ops"] += 1
            if event.status == CacheStatus.HIT:
                stats["hits"] += 1
            elif event.status == CacheStatus.MISS:
                stats["misses"] += 1

            stats["total_latency"] += event.latency_ms

        # Calculate averages
        trends = []
        for hour, stats in sorted(hourly_stats.items()):
            if stats["total_ops"] > 0:
                avg_latency = stats["total_latency"] / stats["total_ops"]
                hit_rate = (stats["hits"] / stats["total_ops"]) * 100

                trends.append({
                    "timestamp": hour.isoformat(),
                    "hit_rate": hit_rate,
                    "avg_latency_ms": avg_latency,
                    "total_operations": stats["total_ops"]
                })

        # Calculate trend direction
        if len(trends) >= 2:
            recent_hit_rates = [t["hit_rate"] for t in trends[-3:]]
            recent_latencies = [t["avg_latency_ms"] for t in trends[-3:]]

            hit_rate_trend = "improving" if recent_hit_rates[-1] > recent_hit_rates[0] else "degrading"
            latency_trend = "improving" if recent_latencies[-1] < recent_latencies[0] else "degrading"
        else:
            hit_rate_trend = latency_trend = "stable"

        return {
            "hourly_trends": trends,
            "hit_rate_trend": hit_rate_trend,
            "latency_trend": latency_trend,
            "analysis_period_hours": hours_back,
            "total_events_analyzed": len(relevant_events)
        }

    # ========================================================================
    # Export and Reporting
    # ========================================================================

    def export_telemetry_report(
        self,
        output_path: Optional[Path] = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export comprehensive telemetry report."""
        # Generate comprehensive report
        all_metrics = self.get_all_layer_metrics()
        health_status = self.assess_cache_health()
        optimization_recommendations = self.generate_optimization_recommendations()
        performance_trends = self.analyze_performance_trends()

        report = {
            "report_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "analysis_window_minutes": self.analysis_window.total_seconds() / 60,
                "total_events": len(self.events),
                "reporting_period": "last_24_hours"
            },
            "cache_layer_metrics": {
                layer.value: asdict(metrics) for layer, metrics in all_metrics.items()
            },
            "health_assessment": asdict(health_status),
            "optimization_recommendations": [asdict(rec) for rec in optimization_recommendations],
            "performance_trends": performance_trends,
            "cache_warming_analysis": {
                layer.value: self.identify_cache_warming_candidates(layer, 10)
                for layer in CacheLayer
            },
            "system_resources": {
                "memory_usage_mb": psutil.virtual_memory().used / 1024 / 1024,
                "cpu_percent": psutil.cpu_percent(),
                "disk_usage_percent": psutil.disk_usage("/").percent
            }
        }

        # Export to file if requested
        if output_path:
            output_path = Path(output_path)
            if format == "json":
                with open(output_path, "w") as f:
                    json.dump(report, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported export format: {format}")

            logger.info(f"Cache telemetry report exported to {output_path}")

        return report

    # ========================================================================
    # Real-time Dashboard Data
    # ========================================================================

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get real-time data for monitoring dashboard."""
        current_metrics = self.get_all_layer_metrics()
        health_status = self.assess_cache_health()

        # Get real-time statistics
        real_time_stats = {}
        for layer in CacheLayer:
            latency_window = list(self.latency_windows[layer])
            throughput_window = list(self.throughput_windows[layer])

            real_time_stats[layer.value] = {
                "current_avg_latency_ms": mean(latency_window) if latency_window else 0,
                "current_p95_latency_ms": (
                    sorted(latency_window)[int(len(latency_window) * 0.95)]
                    if len(latency_window) > 10 else 0
                ),
                "current_throughput": (
                    sum(count for _, count in throughput_window[-5:])  # Last 5 minutes
                    if throughput_window else 0
                ),
                "trend_direction": self._calculate_trend_direction(latency_window)
            }

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "health_status": asdict(health_status),
            "layer_metrics": {
                layer.value: {
                    "hit_rate": metrics.hit_rate_percent,
                    "avg_latency_ms": metrics.avg_latency_ms,
                    "throughput": metrics.throughput_ops_per_sec,
                    "total_size_mb": metrics.total_size_mb,
                    "error_count": metrics.errors
                }
                for layer, metrics in current_metrics.items()
            },
            "real_time_stats": real_time_stats,
            "top_issues": health_status.issues[:5],
            "top_recommendations": [
                rec.description for rec in self.generate_optimization_recommendations()[:3]
            ]
        }

    def _calculate_trend_direction(self, values: List[float]) -> str:
        """Calculate trend direction for a list of values."""
        if len(values) < 5:
            return "stable"

        recent_values = values[-5:]
        older_values = values[-10:-5] if len(values) >= 10 else values[:-5]

        if not older_values:
            return "stable"

        recent_avg = mean(recent_values)
        older_avg = mean(older_values)

        change_percent = ((recent_avg - older_avg) / older_avg) * 100 if older_avg > 0 else 0

        if change_percent > 5:
            return "increasing"
        elif change_percent < -5:
            return "decreasing"
        else:
            return "stable"