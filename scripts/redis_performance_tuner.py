#!/usr/bin/env python3
"""
Redis Performance Tuner
Automated Redis optimization based on workload analysis and performance metrics.
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Union

from redis import Redis
from redis.cluster import RedisCluster

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.metrics_service import MetricsService
from backend.services.redis_cluster_manager import RedisClusterManager

logger = logging.getLogger(__name__)


# ============================================================================
# Performance Analysis Classes
# ============================================================================


@dataclass
class PerformanceMetrics:
    """Redis performance metrics for analysis."""

    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Memory metrics
    used_memory_mb: float = 0.0
    used_memory_peak_mb: float = 0.0
    used_memory_rss_mb: float = 0.0
    memory_fragmentation_ratio: float = 0.0

    # CPU and operations
    instantaneous_ops_per_sec: int = 0
    total_commands_processed: int = 0
    keyspace_hits: int = 0
    keyspace_misses: int = 0
    hit_rate_percent: float = 0.0

    # Connections
    connected_clients: int = 0
    blocked_clients: int = 0
    max_clients: int = 0

    # Persistence
    rdb_changes_since_last_save: int = 0
    rdb_last_save_time: int = 0
    aof_rewrite_in_progress: bool = False
    aof_last_rewrite_time_sec: int = 0

    # Replication
    connected_slaves: int = 0
    master_repl_offset: int = 0
    repl_backlog_active: bool = False

    # Latency
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    slow_queries_count: int = 0

    # Network
    total_net_input_bytes: int = 0
    total_net_output_bytes: int = 0

    def calculate_derived_metrics(self):
        """Calculate derived metrics."""
        # Hit rate
        total_requests = self.keyspace_hits + self.keyspace_misses
        if total_requests > 0:
            self.hit_rate_percent = (self.keyspace_hits / total_requests) * 100

        # Memory efficiency
        if self.used_memory_rss_mb > 0:
            self.memory_fragmentation_ratio = (
                self.used_memory_rss_mb / self.used_memory_mb
            )


@dataclass
class WorkloadPattern:
    """Detected workload pattern."""

    pattern_type: str  # read_heavy, write_heavy, balanced, analytical
    read_write_ratio: float  # reads/writes
    key_access_pattern: str  # uniform, hotspot, sequential
    memory_usage_trend: str  # stable, growing, declining
    peak_hours: list[int] = field(default_factory=list)
    recommended_optimizations: list[str] = field(default_factory=list)


@dataclass
class OptimizationRecommendation:
    """Redis optimization recommendation."""

    category: str  # memory, performance, persistence, replication
    setting: str
    current_value: Any
    recommended_value: Any
    reason: str
    impact: str  # high, medium, low
    risk: str  # low, medium, high

    def to_redis_command(self) -> str:
        """Convert to Redis CONFIG SET command."""
        return f"CONFIG SET {self.setting} {self.recommended_value}"


# ============================================================================
# Redis Performance Tuner
# ============================================================================


class RedisPerformanceTuner:
    """
    Automated Redis performance tuning system.
    """

    def __init__(
        self,
        cluster_manager: RedisClusterManager | None = None,
        metrics_service: MetricsService | None = None,
    ):
        """Initialize performance tuner."""
        self.cluster_manager = cluster_manager
        self.metrics_service = metrics_service

        # Analysis data
        self.historical_metrics: list[PerformanceMetrics] = []
        self.current_workload: WorkloadPattern | None = None
        self.recommendations: list[OptimizationRecommendation] = []

        # Tuning thresholds
        self.thresholds = {
            "memory_fragmentation_threshold": 1.5,
            "hit_rate_threshold": 85.0,  # %
            "cpu_threshold": 80.0,  # %
            "latency_threshold": 10.0,  # ms
            "connection_threshold": 90.0,  # % of max
            "slow_query_threshold": 100,  # ms
        }

        logger.info("Redis Performance Tuner initialized")

    # ========================================================================
    # Metrics Collection
    # ========================================================================

    async def collect_metrics(
        self, client: Union[Redis, RedisCluster]
    ) -> PerformanceMetrics:
        """Collect comprehensive performance metrics from Redis."""
        try:
            # Get Redis info
            info = await asyncio.to_thread(client.info)

            # Create metrics object
            metrics = PerformanceMetrics()

            # Memory metrics
            metrics.used_memory_mb = info.get("used_memory", 0) / 1024 / 1024
            metrics.used_memory_peak_mb = info.get("used_memory_peak", 0) / 1024 / 1024
            metrics.used_memory_rss_mb = info.get("used_memory_rss", 0) / 1024 / 1024

            # Operations metrics
            metrics.instantaneous_ops_per_sec = info.get("instantaneous_ops_per_sec", 0)
            metrics.total_commands_processed = info.get("total_commands_processed", 0)
            metrics.keyspace_hits = info.get("keyspace_hits", 0)
            metrics.keyspace_misses = info.get("keyspace_misses", 0)

            # Connection metrics
            metrics.connected_clients = info.get("connected_clients", 0)
            metrics.blocked_clients = info.get("blocked_clients", 0)
            metrics.max_clients = info.get("maxclients", 10000)

            # Persistence metrics
            metrics.rdb_changes_since_last_save = info.get(
                "rdb_changes_since_last_save", 0
            )
            metrics.rdb_last_save_time = info.get("rdb_last_save_time", 0)
            metrics.aof_rewrite_in_progress = (
                info.get("aof_rewrite_in_progress", 0) == 1
            )
            metrics.aof_last_rewrite_time_sec = info.get("aof_last_rewrite_time_sec", 0)

            # Replication metrics
            metrics.connected_slaves = info.get("connected_slaves", 0)
            metrics.master_repl_offset = info.get("master_repl_offset", 0)
            metrics.repl_backlog_active = info.get("repl_backlog_active", 0) == 1

            # Network metrics
            metrics.total_net_input_bytes = info.get("total_net_input_bytes", 0)
            metrics.total_net_output_bytes = info.get("total_net_output_bytes", 0)

            # Get latency info
            try:
                latency_history = await asyncio.to_thread(
                    client.latency_history, "command"
                )
                if latency_history:
                    metrics.avg_latency_ms = sum(
                        item[1] for item in latency_history
                    ) / len(latency_history)
                    metrics.p99_latency_ms = sorted(
                        [item[1] for item in latency_history]
                    )[int(len(latency_history) * 0.99)]
            except:
                pass  # Latency history might not be available

            # Get slow log
            try:
                slow_log = await asyncio.to_thread(client.slowlog_get, 10)
                metrics.slow_queries_count = len(slow_log)
            except:
                pass

            # Calculate derived metrics
            metrics.calculate_derived_metrics()

            return metrics

        except Exception as e:
            logger.error(f"Error collecting Redis metrics: {e}")
            return PerformanceMetrics()  # Return empty metrics

    async def analyze_workload_pattern(self) -> WorkloadPattern:
        """Analyze workload patterns from historical metrics."""
        if len(self.historical_metrics) < 10:
            return WorkloadPattern(
                pattern_type="unknown",
                read_write_ratio=1.0,
                key_access_pattern="uniform",
                memory_usage_trend="stable",
            )

        # Calculate read/write ratio
        recent_metrics = self.historical_metrics[-10:]
        avg_hits = sum(m.keyspace_hits for m in recent_metrics) / len(recent_metrics)
        avg_ops = sum(m.instantaneous_ops_per_sec for m in recent_metrics) / len(
            recent_metrics
        )

        # Estimate read/write ratio (hits indicate reads)
        read_write_ratio = avg_hits / max(avg_ops - avg_hits, 1)

        # Determine pattern type
        if read_write_ratio > 4:
            pattern_type = "read_heavy"
        elif read_write_ratio < 0.5:
            pattern_type = "write_heavy"
        else:
            pattern_type = "balanced"

        # Analyze memory trend
        memory_values = [m.used_memory_mb for m in recent_metrics]
        if len(memory_values) > 1:
            memory_trend = (memory_values[-1] - memory_values[0]) / memory_values[0]
            if memory_trend > 0.1:
                memory_usage_trend = "growing"
            elif memory_trend < -0.1:
                memory_usage_trend = "declining"
            else:
                memory_usage_trend = "stable"
        else:
            memory_usage_trend = "stable"

        # Generate recommendations based on pattern
        recommendations = []
        if pattern_type == "read_heavy":
            recommendations.extend(
                [
                    "Increase maxmemory-samples for better LRU",
                    "Consider read replicas for scaling",
                    "Optimize key expiration policies",
                ]
            )
        elif pattern_type == "write_heavy":
            recommendations.extend(
                [
                    "Tune AOF settings for write performance",
                    "Consider increasing save intervals",
                    "Optimize memory allocation",
                ]
            )

        return WorkloadPattern(
            pattern_type=pattern_type,
            read_write_ratio=read_write_ratio,
            key_access_pattern="uniform",  # Would need more analysis
            memory_usage_trend=memory_usage_trend,
            recommended_optimizations=recommendations,
        )

    # ========================================================================
    # Performance Analysis
    # ========================================================================

    def analyze_performance(
        self, metrics: PerformanceMetrics
    ) -> list[OptimizationRecommendation]:
        """Analyze performance metrics and generate recommendations."""
        recommendations = []

        # Memory analysis
        if (
            metrics.memory_fragmentation_ratio
            > self.thresholds["memory_fragmentation_threshold"]
        ):
            recommendations.append(
                OptimizationRecommendation(
                    category="memory",
                    setting="activedefrag",
                    current_value="no",
                    recommended_value="yes",
                    reason=f"High memory fragmentation ratio: {metrics.memory_fragmentation_ratio:.2f}",
                    impact="medium",
                    risk="low",
                )
            )

        # Hit rate analysis
        if metrics.hit_rate_percent < self.thresholds["hit_rate_threshold"]:
            recommendations.append(
                OptimizationRecommendation(
                    category="memory",
                    setting="maxmemory-policy",
                    current_value="noeviction",
                    recommended_value="allkeys-lru",
                    reason=f"Low cache hit rate: {metrics.hit_rate_percent:.1f}%",
                    impact="high",
                    risk="low",
                )
            )

            recommendations.append(
                OptimizationRecommendation(
                    category="memory",
                    setting="maxmemory-samples",
                    current_value="5",
                    recommended_value="10",
                    reason="Improve LRU precision for better cache efficiency",
                    impact="medium",
                    risk="low",
                )
            )

        # Connection analysis
        connection_usage = (metrics.connected_clients / metrics.max_clients) * 100
        if connection_usage > self.thresholds["connection_threshold"]:
            new_max = int(metrics.max_clients * 1.5)
            recommendations.append(
                OptimizationRecommendation(
                    category="performance",
                    setting="maxclients",
                    current_value=str(metrics.max_clients),
                    recommended_value=str(new_max),
                    reason=f"High connection usage: {connection_usage:.1f}%",
                    impact="medium",
                    risk="low",
                )
            )

        # Latency analysis
        if metrics.avg_latency_ms > self.thresholds["latency_threshold"]:
            recommendations.append(
                OptimizationRecommendation(
                    category="performance",
                    setting="tcp-keepalive",
                    current_value="300",
                    recommended_value="60",
                    reason=f"High average latency: {metrics.avg_latency_ms:.2f}ms",
                    impact="medium",
                    risk="low",
                )
            )

        # Slow queries analysis
        if metrics.slow_queries_count > 0:
            recommendations.append(
                OptimizationRecommendation(
                    category="performance",
                    setting="slowlog-max-len",
                    current_value="128",
                    recommended_value="1000",
                    reason=f"Detected {metrics.slow_queries_count} slow queries",
                    impact="low",
                    risk="low",
                )
            )

        # Persistence optimization
        if metrics.rdb_changes_since_last_save > 10000:
            recommendations.append(
                OptimizationRecommendation(
                    category="persistence",
                    setting="save",
                    current_value="900 1 300 10 60 10000",
                    recommended_value="1800 1 300 100 60 10000",
                    reason=f"High unsaved changes: {metrics.rdb_changes_since_last_save}",
                    impact="medium",
                    risk="medium",
                )
            )

        # AOF optimization for write-heavy workloads
        if (
            self.current_workload
            and self.current_workload.pattern_type == "write_heavy"
        ):
            recommendations.append(
                OptimizationRecommendation(
                    category="persistence",
                    setting="auto-aof-rewrite-percentage",
                    current_value="100",
                    recommended_value="50",
                    reason="Optimize AOF for write-heavy workload",
                    impact="medium",
                    risk="low",
                )
            )

        return recommendations

    # ========================================================================
    # Configuration Optimization
    # ========================================================================

    async def apply_recommendations(
        self,
        client: Union[Redis, RedisCluster],
        recommendations: list[OptimizationRecommendation],
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Apply optimization recommendations to Redis."""
        results = {"applied": [], "failed": [], "skipped": [], "dry_run": dry_run}

        for rec in recommendations:
            try:
                if dry_run:
                    # Just validate the command would work
                    command = rec.to_redis_command()
                    results["applied"].append(
                        {
                            "recommendation": rec,
                            "command": command,
                            "status": "would_apply",
                        }
                    )
                else:
                    # Apply the configuration
                    if rec.risk == "high":
                        results["skipped"].append(
                            {
                                "recommendation": rec,
                                "reason": "High risk - manual review required",
                            }
                        )
                        continue

                    await asyncio.to_thread(
                        client.config_set, rec.setting, rec.recommended_value
                    )

                    results["applied"].append(
                        {
                            "recommendation": rec,
                            "command": rec.to_redis_command(),
                            "status": "applied",
                        }
                    )

                    logger.info(
                        f"Applied optimization: {rec.setting} = {rec.recommended_value}"
                    )

            except Exception as e:
                results["failed"].append({"recommendation": rec, "error": str(e)})
                logger.error(f"Failed to apply recommendation {rec.setting}: {e}")

        return results

    async def get_current_config(
        self, client: Union[Redis, RedisCluster]
    ) -> dict[str, str]:
        """Get current Redis configuration."""
        try:
            config = await asyncio.to_thread(client.config_get, "*")
            return dict(zip(config[::2], config[1::2], strict=False))
        except Exception as e:
            logger.error(f"Failed to get Redis config: {e}")
            return {}

    async def backup_config(self, client: Union[Redis, RedisCluster]) -> str:
        """Backup current Redis configuration."""
        config = await self.get_current_config(client)

        backup_data = {"timestamp": datetime.utcnow().isoformat(), "config": config}

        # Save backup to file
        backup_file = f"redis_config_backup_{int(time.time())}.json"
        with open(backup_file, "w") as f:
            json.dump(backup_data, f, indent=2)

        logger.info(f"Redis configuration backed up to {backup_file}")
        return backup_file

    # ========================================================================
    # Performance Monitoring
    # ========================================================================

    async def run_continuous_tuning(
        self,
        client: Union[Redis, RedisCluster],
        interval_minutes: int = 60,
        auto_apply: bool = False,
    ):
        """Run continuous performance monitoring and tuning."""
        logger.info(
            f"Starting continuous tuning (interval: {interval_minutes}min, auto_apply: {auto_apply})"
        )

        while True:
            try:
                # Collect metrics
                metrics = await self.collect_metrics(client)
                self.historical_metrics.append(metrics)

                # Keep only recent history (last 24 hours)
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                self.historical_metrics = [
                    m for m in self.historical_metrics if m.timestamp > cutoff_time
                ]

                # Analyze workload pattern
                self.current_workload = await self.analyze_workload_pattern()

                # Generate recommendations
                recommendations = self.analyze_performance(metrics)
                self.recommendations = recommendations

                # Log current status
                logger.info(
                    f"Performance Analysis - "
                    f"Hit Rate: {metrics.hit_rate_percent:.1f}%, "
                    f"Memory: {metrics.used_memory_mb:.1f}MB, "
                    f"Clients: {metrics.connected_clients}, "
                    f"OPS: {metrics.instantaneous_ops_per_sec}"
                )

                # Apply recommendations if enabled
                if auto_apply and recommendations:
                    # Only apply low-risk recommendations automatically
                    safe_recommendations = [
                        r for r in recommendations if r.risk == "low"
                    ]

                    if safe_recommendations:
                        await self.backup_config(client)
                        results = await self.apply_recommendations(
                            client, safe_recommendations, dry_run=False
                        )
                        logger.info(
                            f"Auto-applied {len(results['applied'])} optimizations"
                        )

                # Report metrics to monitoring system
                if self.metrics_service:
                    self.metrics_service.record_cache_operation(
                        operation="health_check",
                        cache_type="redis",
                        hit=True if metrics.hit_rate_percent > 80 else False,
                    )
                    self.metrics_service.update_cache_size(
                        "redis", int(metrics.used_memory_mb * 1024 * 1024)
                    )

                # Wait for next interval
                await asyncio.sleep(interval_minutes * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in continuous tuning: {e}")
                await asyncio.sleep(60)  # Short delay on error

    # ========================================================================
    # Reporting
    # ========================================================================

    def generate_performance_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self.historical_metrics:
            return {"error": "No metrics available"}

        latest = self.historical_metrics[-1]

        # Calculate trends
        if len(self.historical_metrics) >= 2:
            previous = self.historical_metrics[-2]
            trends = {
                "memory_trend": latest.used_memory_mb - previous.used_memory_mb,
                "ops_trend": latest.instantaneous_ops_per_sec
                - previous.instantaneous_ops_per_sec,
                "hit_rate_trend": latest.hit_rate_percent - previous.hit_rate_percent,
            }
        else:
            trends = {"memory_trend": 0, "ops_trend": 0, "hit_rate_trend": 0}

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "overall_health": (
                    "good" if latest.hit_rate_percent > 80 else "needs_attention"
                ),
                "total_recommendations": len(self.recommendations),
                "high_priority_issues": len(
                    [r for r in self.recommendations if r.impact == "high"]
                ),
            },
            "current_metrics": {
                "memory_usage_mb": latest.used_memory_mb,
                "hit_rate_percent": latest.hit_rate_percent,
                "operations_per_sec": latest.instantaneous_ops_per_sec,
                "connected_clients": latest.connected_clients,
                "memory_fragmentation": latest.memory_fragmentation_ratio,
                "avg_latency_ms": latest.avg_latency_ms,
            },
            "trends": trends,
            "workload_pattern": {
                "type": (
                    self.current_workload.pattern_type
                    if self.current_workload
                    else "unknown"
                ),
                "read_write_ratio": (
                    self.current_workload.read_write_ratio
                    if self.current_workload
                    else 1.0
                ),
            },
            "recommendations": [
                {
                    "category": r.category,
                    "setting": r.setting,
                    "current": r.current_value,
                    "recommended": r.recommended_value,
                    "reason": r.reason,
                    "impact": r.impact,
                    "risk": r.risk,
                }
                for r in self.recommendations
            ],
            "historical_data": {
                "data_points": len(self.historical_metrics),
                "time_range_hours": (
                    (
                        self.historical_metrics[-1].timestamp
                        - self.historical_metrics[0].timestamp
                    ).total_seconds()
                    / 3600
                    if len(self.historical_metrics) > 1
                    else 0
                ),
            },
        }

        return report


# ============================================================================
# Command Line Interface
# ============================================================================


async def main():
    """Main function for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Redis Performance Tuner")
    parser.add_argument("--host", default="localhost", help="Redis host")
    parser.add_argument("--port", type=int, default=6379, help="Redis port")
    parser.add_argument("--password", help="Redis password")
    parser.add_argument(
        "--analyze", action="store_true", help="Run performance analysis"
    )
    parser.add_argument(
        "--continuous", action="store_true", help="Run continuous monitoring"
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="Monitoring interval in minutes"
    )
    parser.add_argument(
        "--auto-apply", action="store_true", help="Auto-apply safe recommendations"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show recommendations without applying"
    )
    parser.add_argument("--output", help="Output file for report")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        # Create Redis client
        client = Redis(
            host=args.host,
            port=args.port,
            password=args.password,
            decode_responses=False,
        )

        # Test connection
        await asyncio.to_thread(client.ping)
        print(f"Connected to Redis at {args.host}:{args.port}")

        # Create tuner
        tuner = RedisPerformanceTuner()

        if args.analyze:
            # Single analysis run
            print("Collecting metrics...")
            metrics = await tuner.collect_metrics(client)

            print("Analyzing performance...")
            recommendations = tuner.analyze_performance(metrics)
            tuner.recommendations = recommendations

            # Generate report
            report = tuner.generate_performance_report()

            if args.output:
                with open(args.output, "w") as f:
                    json.dump(report, f, indent=2)
                print(f"Report saved to {args.output}")
            else:
                print(json.dumps(report, indent=2))

            # Apply recommendations if requested
            if recommendations and not args.dry_run:
                print(f"\nFound {len(recommendations)} recommendations")
                apply = input("Apply recommendations? [y/N]: ").lower().startswith("y")

                if apply:
                    await tuner.backup_config(client)
                    results = await tuner.apply_recommendations(
                        client, recommendations, dry_run=False
                    )
                    print(f"Applied {len(results['applied'])} optimizations")
                    print(
                        f"Failed: {len(results['failed'])}, Skipped: {len(results['skipped'])}"
                    )

        elif args.continuous:
            # Continuous monitoring
            print(f"Starting continuous monitoring (interval: {args.interval}min)")
            await tuner.run_continuous_tuning(
                client, interval_minutes=args.interval, auto_apply=args.auto_apply
            )

        else:
            print("Use --analyze for single analysis or --continuous for monitoring")
            print("Use --help for more options")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
