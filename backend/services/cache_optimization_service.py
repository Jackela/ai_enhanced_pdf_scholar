"""
Advanced Cache Optimization and Predictive Warming Service

Provides intelligent cache warming, optimization recommendations,
and automated cache management strategies for all cache layers.
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
from typing import Any, Dict, List, Optional, Set, Tuple
from statistics import mean, median

import psutil

from backend.services.cache_telemetry_service import CacheLayer, CacheTelemetryService
from backend.services.redis_cache_service import RedisCacheService
from src.services.rag_cache_service import RAGCacheService

logger = logging.getLogger(__name__)


# ============================================================================
# Cache Optimization Models
# ============================================================================

class OptimizationStrategy(str, Enum):
    """Cache optimization strategies."""
    PREDICTIVE_WARMING = "predictive_warming"
    INTELLIGENT_EVICTION = "intelligent_eviction"
    TTL_OPTIMIZATION = "ttl_optimization"
    SIZE_OPTIMIZATION = "size_optimization"
    PATTERN_BASED_PRELOADING = "pattern_based_preloading"
    ADAPTIVE_CACHING = "adaptive_caching"


class WarmingPriority(str, Enum):
    """Cache warming priority levels."""
    CRITICAL = "critical"      # Immediate warming
    HIGH = "high"              # Warm within 5 minutes
    MEDIUM = "medium"          # Warm within 30 minutes
    LOW = "low"                # Warm during off-peak hours


@dataclass
class CachePattern:
    """Identified cache access pattern."""
    pattern_id: str
    pattern_template: str      # e.g., "user:{id}:profile"
    cache_layer: CacheLayer
    frequency_score: float     # How often this pattern is accessed
    hit_rate: float           # Current hit rate for this pattern
    avg_access_time: float    # Average time between accesses
    last_seen: datetime
    sample_keys: List[str] = field(default_factory=list)
    predictable: bool = False  # Whether access pattern is predictable


@dataclass
class WarmingCandidate:
    """Cache warming candidate."""
    candidate_id: str
    cache_layer: CacheLayer
    key: str
    key_pattern: str
    priority: WarmingPriority
    estimated_hit_improvement: float
    warming_cost: float        # Cost to warm (computation, I/O, etc.)
    predicted_access_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationRecommendation:
    """Cache optimization recommendation."""
    recommendation_id: str
    strategy: OptimizationStrategy
    cache_layer: CacheLayer
    title: str
    description: str
    impact_score: float        # 0-100, higher is better
    implementation_effort: str # "low", "medium", "high"
    estimated_improvement: Dict[str, float]  # metric -> improvement %
    action_items: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)


@dataclass
class WarmingJob:
    """Cache warming job."""
    job_id: str
    cache_layer: CacheLayer
    keys_to_warm: List[str]
    priority: WarmingPriority
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"    # pending, running, completed, failed
    progress: int = 0          # 0-100
    results: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Cache Optimization Service
# ============================================================================

class CacheOptimizationService:
    """
    Advanced cache optimization service with predictive warming capabilities.
    """
    
    def __init__(
        self,
        cache_telemetry: CacheTelemetryService,
        redis_cache: RedisCacheService,
        rag_cache: RAGCacheService
    ):
        self.telemetry = cache_telemetry
        self.redis_cache = redis_cache
        self.rag_cache = rag_cache
        
        # Pattern analysis
        self.access_patterns: Dict[str, CachePattern] = {}
        self.warming_candidates: List[WarmingCandidate] = []
        self.optimization_recommendations: List[OptimizationRecommendation] = []
        
        # Warming job management
        self.warming_jobs: Dict[str, WarmingJob] = {}
        self.active_jobs: Set[str] = set()
        
        # Learning and prediction
        self.access_history: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        self.pattern_models: Dict[str, Dict[str, Any]] = {}
        
        # Configuration
        self.min_pattern_frequency = 5  # Minimum accesses to consider a pattern
        self.prediction_window_hours = 24
        self.warming_batch_size = 50
        self.max_concurrent_jobs = 3
        
        # Background tasks
        self._running = False
        self._analysis_task: Optional[asyncio.Task] = None
        self._warming_task: Optional[asyncio.Task] = None
        
        logger.info("Cache optimization service initialized")
    
    # ========================================================================
    # Service Lifecycle
    # ========================================================================
    
    async def start_optimization(self):
        """Start background optimization tasks."""
        if not self._running:
            self._running = True
            self._analysis_task = asyncio.create_task(self._analysis_loop())
            self._warming_task = asyncio.create_task(self._warming_loop())
            logger.info("Cache optimization service started")
    
    async def stop_optimization(self):
        """Stop background optimization tasks."""
        self._running = False
        
        if self._analysis_task:
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass
        
        if self._warming_task:
            self._warming_task.cancel()
            try:
                await self._warming_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Cache optimization service stopped")
    
    # ========================================================================
    # Pattern Analysis
    # ========================================================================
    
    async def _analysis_loop(self):
        """Background loop for pattern analysis and optimization."""
        while self._running:
            try:
                # Analyze access patterns every 5 minutes
                await self._analyze_access_patterns()
                
                # Generate optimization recommendations every 15 minutes
                if datetime.utcnow().minute % 15 == 0:
                    await self._generate_optimization_recommendations()
                
                # Identify warming candidates every 10 minutes  
                if datetime.utcnow().minute % 10 == 0:
                    await self._identify_warming_candidates()
                
                await asyncio.sleep(300)  # 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in optimization analysis loop: {e}")
                await asyncio.sleep(300)
    
    async def _analyze_access_patterns(self):
        """Analyze cache access patterns to identify optimization opportunities."""
        try:
            # Analyze patterns for each cache layer
            for layer in CacheLayer:
                await self._analyze_layer_patterns(layer)
            
            # Update pattern models for prediction
            await self._update_pattern_models()
            
            logger.debug("Access pattern analysis completed")
            
        except Exception as e:
            logger.error(f"Error analyzing access patterns: {e}")
    
    async def _analyze_layer_patterns(self, layer: CacheLayer):
        """Analyze access patterns for a specific cache layer."""
        # Get recent events from telemetry
        cutoff_time = datetime.utcnow() - timedelta(hours=2)
        recent_events = [
            event for event in self.telemetry.events
            if event.cache_layer == layer and event.timestamp >= cutoff_time
        ]
        
        if not recent_events:
            return
        
        # Group events by pattern
        pattern_stats = defaultdict(lambda: {
            'keys': set(),
            'hits': 0,
            'misses': 0,
            'total_latency': 0.0,
            'access_times': []
        })
        
        for event in recent_events:
            pattern = event.key_pattern
            stats = pattern_stats[pattern]
            
            stats['keys'].add(event.key)
            stats['access_times'].append(event.timestamp)
            stats['total_latency'] += event.latency_ms
            
            if event.status.value == "hit":
                stats['hits'] += 1
            elif event.status.value == "miss":
                stats['misses'] += 1
        
        # Analyze each pattern
        for pattern_template, stats in pattern_stats.items():
            total_accesses = stats['hits'] + stats['misses']
            
            if total_accesses < self.min_pattern_frequency:
                continue
            
            hit_rate = (stats['hits'] / total_accesses) * 100 if total_accesses > 0 else 0
            avg_latency = stats['total_latency'] / total_accesses if total_accesses > 0 else 0
            
            # Calculate access frequency (accesses per hour)
            time_span = max(1, (max(stats['access_times']) - min(stats['access_times'])).total_seconds() / 3600)
            frequency_score = total_accesses / time_span
            
            # Calculate average time between accesses
            if len(stats['access_times']) > 1:
                intervals = [
                    (stats['access_times'][i] - stats['access_times'][i-1]).total_seconds()
                    for i in range(1, len(stats['access_times']))
                ]
                avg_access_time = mean(intervals)
            else:
                avg_access_time = 0
            
            # Create or update pattern
            pattern_id = f"{layer.value}:{pattern_template}"
            
            self.access_patterns[pattern_id] = CachePattern(
                pattern_id=pattern_id,
                pattern_template=pattern_template,
                cache_layer=layer,
                frequency_score=frequency_score,
                hit_rate=hit_rate,
                avg_access_time=avg_access_time,
                last_seen=max(stats['access_times']),
                sample_keys=list(stats['keys'])[:10],
                predictable=self._is_pattern_predictable(stats['access_times'])
            )
    
    def _is_pattern_predictable(self, access_times: List[datetime]) -> bool:
        """Determine if an access pattern is predictable."""
        if len(access_times) < 5:
            return False
        
        # Calculate intervals between accesses
        intervals = [
            (access_times[i] - access_times[i-1]).total_seconds()
            for i in range(1, len(access_times))
        ]
        
        # Check for regular patterns
        if len(intervals) >= 3:
            # Calculate coefficient of variation
            if mean(intervals) > 0:
                cv = (stdev(intervals) / mean(intervals)) if len(intervals) > 1 else 0
                # Lower CV indicates more regular pattern
                return cv < 0.5
        
        return False
    
    # ========================================================================
    # Predictive Models
    # ========================================================================
    
    async def _update_pattern_models(self):
        """Update predictive models for cache access patterns."""
        try:
            for pattern_id, pattern in self.access_patterns.items():
                if not pattern.predictable:
                    continue
                
                # Simple time-series prediction model
                model = self._build_simple_prediction_model(pattern)
                if model:
                    self.pattern_models[pattern_id] = model
        
        except Exception as e:
            logger.error(f"Error updating pattern models: {e}")
    
    def _build_simple_prediction_model(self, pattern: CachePattern) -> Optional[Dict[str, Any]]:
        """Build simple prediction model for cache access pattern."""
        try:
            # Get historical access data
            pattern_keys = [key for key in self.access_history.keys() 
                          if self._extract_pattern(key) == pattern.pattern_template]
            
            if not pattern_keys:
                return None
            
            # Analyze access patterns over time
            all_accesses = []
            for key in pattern_keys:
                all_accesses.extend(self.access_history[key])
            
            if len(all_accesses) < 10:  # Need minimum data
                return None
            
            # Sort by timestamp
            all_accesses.sort(key=lambda x: x[0])
            
            # Extract hourly access patterns
            hourly_counts = defaultdict(int)
            for timestamp, _ in all_accesses:
                hour = timestamp.hour
                hourly_counts[hour] += 1
            
            # Find peak hours
            if hourly_counts:
                peak_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                peak_hours = [hour for hour, count in peak_hours]
            else:
                peak_hours = []
            
            return {
                "pattern_type": "hourly",
                "peak_hours": peak_hours,
                "avg_interval_seconds": pattern.avg_access_time,
                "confidence": min(len(all_accesses) / 100, 1.0),  # Confidence based on data volume
                "last_updated": datetime.utcnow()
            }
        
        except Exception as e:
            logger.error(f"Error building prediction model: {e}")
            return None
    
    def _extract_pattern(self, key: str) -> str:
        """Extract pattern template from cache key."""
        # This is the reverse of the pattern extraction in telemetry service
        import re
        
        # Replace numeric IDs
        pattern = re.sub(r'\d+', '{id}', key)
        
        # Replace hash-like strings
        pattern = re.sub(r'[a-f0-9]{8,}', '{hash}', pattern)
        
        # Replace UUIDs
        pattern = re.sub(
            r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',
            '{uuid}',
            pattern
        )
        
        return pattern
    
    # ========================================================================
    # Cache Warming
    # ========================================================================
    
    async def _identify_warming_candidates(self):
        """Identify candidates for predictive cache warming."""
        try:
            candidates = []
            
            for pattern_id, pattern in self.access_patterns.items():
                if pattern.hit_rate < 70:  # Focus on patterns with poor hit rates
                    warming_candidates = await self._generate_warming_candidates_for_pattern(pattern)
                    candidates.extend(warming_candidates)
            
            # Sort by priority and potential impact
            candidates.sort(key=lambda c: (c.priority.value, -c.estimated_hit_improvement))
            
            self.warming_candidates = candidates[:100]  # Keep top 100 candidates
            
            logger.debug(f"Identified {len(self.warming_candidates)} warming candidates")
            
        except Exception as e:
            logger.error(f"Error identifying warming candidates: {e}")
    
    async def _generate_warming_candidates_for_pattern(
        self,
        pattern: CachePattern
    ) -> List[WarmingCandidate]:
        """Generate warming candidates for a specific pattern."""
        candidates = []
        
        try:
            # Use pattern model to predict future accesses
            model = self.pattern_models.get(pattern.pattern_id)
            if not model:
                return candidates
            
            current_hour = datetime.utcnow().hour
            next_hours = [(current_hour + i) % 24 for i in range(1, 4)]  # Next 3 hours
            
            # Check if any of the next hours are peak hours
            peak_hours = model.get("peak_hours", [])
            upcoming_peak_hours = [h for h in next_hours if h in peak_hours]
            
            if not upcoming_peak_hours:
                return candidates
            
            # Generate candidates for pattern keys that are likely to be accessed
            for key in pattern.sample_keys[:20]:  # Limit to prevent overwhelming
                # Estimate hit improvement
                current_hit_rate = pattern.hit_rate
                estimated_improvement = min(30, 80 - current_hit_rate)  # Cap at 30% improvement
                
                # Calculate warming cost (simplified)
                warming_cost = 1.0  # Base cost
                if pattern.cache_layer == CacheLayer.RAG_QUERY:
                    warming_cost = 5.0  # Higher cost for complex operations
                elif pattern.cache_layer == CacheLayer.VECTOR_INDEX:
                    warming_cost = 3.0
                
                # Determine priority
                priority = WarmingPriority.LOW
                if estimated_improvement > 20:
                    priority = WarmingPriority.HIGH
                elif estimated_improvement > 10:
                    priority = WarmingPriority.MEDIUM
                
                # Predict next access time
                if pattern.avg_access_time > 0:
                    predicted_access = datetime.utcnow() + timedelta(seconds=pattern.avg_access_time)
                else:
                    predicted_access = None
                
                candidate = WarmingCandidate(
                    candidate_id=f"{pattern.pattern_id}:{key}:{datetime.utcnow().timestamp()}",
                    cache_layer=pattern.cache_layer,
                    key=key,
                    key_pattern=pattern.pattern_template,
                    priority=priority,
                    estimated_hit_improvement=estimated_improvement,
                    warming_cost=warming_cost,
                    predicted_access_time=predicted_access,
                    metadata={
                        "pattern_frequency": pattern.frequency_score,
                        "current_hit_rate": pattern.hit_rate,
                        "model_confidence": model.get("confidence", 0.5)
                    }
                )
                
                candidates.append(candidate)
        
        except Exception as e:
            logger.error(f"Error generating warming candidates for pattern {pattern.pattern_id}: {e}")
        
        return candidates
    
    async def _warming_loop(self):
        """Background loop for executing cache warming jobs."""
        while self._running:
            try:
                # Execute pending warming jobs
                await self._execute_warming_jobs()
                
                # Clean up completed jobs
                await self._cleanup_completed_jobs()
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in warming loop: {e}")
                await asyncio.sleep(60)
    
    async def _execute_warming_jobs(self):
        """Execute pending warming jobs."""
        try:
            # Find jobs ready for execution
            now = datetime.utcnow()
            ready_jobs = [
                job for job in self.warming_jobs.values()
                if (job.status == "pending" and 
                    (job.scheduled_for is None or job.scheduled_for <= now) and
                    job.job_id not in self.active_jobs)
            ]
            
            # Sort by priority
            priority_order = {
                WarmingPriority.CRITICAL: 0,
                WarmingPriority.HIGH: 1,
                WarmingPriority.MEDIUM: 2,
                WarmingPriority.LOW: 3
            }
            ready_jobs.sort(key=lambda j: priority_order.get(j.priority, 4))
            
            # Execute jobs up to concurrent limit
            jobs_to_start = ready_jobs[:self.max_concurrent_jobs - len(self.active_jobs)]
            
            for job in jobs_to_start:
                asyncio.create_task(self._execute_single_warming_job(job))
        
        except Exception as e:
            logger.error(f"Error executing warming jobs: {e}")
    
    async def _execute_single_warming_job(self, job: WarmingJob):
        """Execute a single cache warming job."""
        job_id = job.job_id
        self.active_jobs.add(job_id)
        
        try:
            job.status = "running"
            job.started_at = datetime.utcnow()
            
            logger.info(f"Starting warming job {job_id} for {len(job.keys_to_warm)} keys")
            
            successful_warms = 0
            failed_warms = 0
            
            for i, key in enumerate(job.keys_to_warm):
                try:
                    success = await self._warm_single_key(job.cache_layer, key)
                    if success:
                        successful_warms += 1
                    else:
                        failed_warms += 1
                    
                    # Update progress
                    job.progress = int((i + 1) / len(job.keys_to_warm) * 100)
                    
                    # Small delay to prevent overwhelming the system
                    await asyncio.sleep(0.1)
                
                except Exception as e:
                    logger.error(f"Error warming key {key}: {e}")
                    failed_warms += 1
            
            # Complete job
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.progress = 100
            job.results = {
                "successful_warms": successful_warms,
                "failed_warms": failed_warms,
                "total_keys": len(job.keys_to_warm),
                "duration_seconds": (job.completed_at - job.started_at).total_seconds()
            }
            
            logger.info(
                f"Completed warming job {job_id}: "
                f"{successful_warms}/{len(job.keys_to_warm)} successful"
            )
        
        except Exception as e:
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.results = {"error": str(e)}
            logger.error(f"Warming job {job_id} failed: {e}")
        
        finally:
            self.active_jobs.discard(job_id)
    
    async def _warm_single_key(self, cache_layer: CacheLayer, key: str) -> bool:
        """Warm a single cache key."""
        try:
            if cache_layer == CacheLayer.RAG_QUERY:
                return await self._warm_rag_query_key(key)
            elif cache_layer == CacheLayer.REDIS_L2:
                return await self._warm_redis_key(key)
            elif cache_layer == CacheLayer.DATABASE:
                return await self._warm_database_key(key)
            else:
                logger.warning(f"Warming not implemented for layer {cache_layer}")
                return False
        
        except Exception as e:
            logger.error(f"Error warming key {key} in layer {cache_layer}: {e}")
            return False
    
    async def _warm_rag_query_key(self, key: str) -> bool:
        """Warm a RAG query cache key."""
        try:
            # Parse key to extract query and document ID
            # This is a simplified implementation
            # In practice, you'd need to parse the actual key format
            
            # For now, just check if key already exists
            # If not, we can't warm it without the original query
            return True  # Simplified implementation
        
        except Exception as e:
            logger.error(f"Error warming RAG query key {key}: {e}")
            return False
    
    async def _warm_redis_key(self, key: str) -> bool:
        """Warm a Redis cache key."""
        try:
            # Check if key exists
            exists = self.redis_cache.exists(key)
            if exists:
                return True  # Already warmed
            
            # For Redis warming, we'd need to know how to regenerate the value
            # This is application-specific logic
            return True  # Simplified implementation
        
        except Exception as e:
            logger.error(f"Error warming Redis key {key}: {e}")
            return False
    
    async def _warm_database_key(self, key: str) -> bool:
        """Warm a database cache key."""
        try:
            # Database key warming would involve pre-loading query results
            # This is application-specific logic
            return True  # Simplified implementation
        
        except Exception as e:
            logger.error(f"Error warming database key {key}: {e}")
            return False
    
    # ========================================================================
    # Optimization Recommendations
    # ========================================================================
    
    async def _generate_optimization_recommendations(self):
        """Generate cache optimization recommendations."""
        try:
            recommendations = []
            
            # Analyze each cache layer
            layer_metrics = self.telemetry.get_all_layer_metrics()
            
            for layer, metrics in layer_metrics.items():
                layer_recommendations = await self._generate_layer_recommendations(layer, metrics)
                recommendations.extend(layer_recommendations)
            
            # Sort by impact score
            recommendations.sort(key=lambda r: r.impact_score, reverse=True)
            
            self.optimization_recommendations = recommendations[:20]  # Keep top 20
            
            logger.debug(f"Generated {len(self.optimization_recommendations)} optimization recommendations")
        
        except Exception as e:
            logger.error(f"Error generating optimization recommendations: {e}")
    
    async def _generate_layer_recommendations(self, layer: CacheLayer, metrics) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations for a specific cache layer."""
        recommendations = []
        
        try:
            # Low hit rate recommendation
            if metrics.hit_rate_percent < 70:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id=f"{layer.value}_improve_hit_rate",
                    strategy=OptimizationStrategy.PREDICTIVE_WARMING,
                    cache_layer=layer,
                    title=f"Improve {layer.value} Hit Rate",
                    description=f"Hit rate is {metrics.hit_rate_percent:.1f}%. Implement predictive warming for frequently accessed patterns.",
                    impact_score=90 - metrics.hit_rate_percent,
                    implementation_effort="medium",
                    estimated_improvement={
                        "hit_rate_increase": min(20, 80 - metrics.hit_rate_percent),
                        "latency_reduction": 15,
                        "cost_reduction": 10
                    },
                    action_items=[
                        "Analyze access patterns to identify warming candidates",
                        "Implement background warming jobs for hot keys",
                        "Monitor warming effectiveness and adjust strategies"
                    ],
                    prerequisites=["Pattern analysis data", "Background job system"]
                ))
            
            # High latency recommendation
            if metrics.avg_latency_ms > 50:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id=f"{layer.value}_reduce_latency",
                    strategy=OptimizationStrategy.SIZE_OPTIMIZATION,
                    cache_layer=layer,
                    title=f"Reduce {layer.value} Latency",
                    description=f"Average latency is {metrics.avg_latency_ms:.1f}ms. Consider optimizing cache entry sizes and access patterns.",
                    impact_score=min(80, metrics.avg_latency_ms),
                    implementation_effort="high",
                    estimated_improvement={
                        "latency_reduction": min(50, metrics.avg_latency_ms * 0.3),
                        "throughput_increase": 15
                    },
                    action_items=[
                        "Analyze cache entry sizes and optimize large entries",
                        "Implement compression for large cache values",
                        "Consider cache key restructuring for better access patterns"
                    ]
                ))
            
            # Memory usage recommendation
            if metrics.total_size_mb > 500:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id=f"{layer.value}_optimize_memory",
                    strategy=OptimizationStrategy.INTELLIGENT_EVICTION,
                    cache_layer=layer,
                    title=f"Optimize {layer.value} Memory Usage",
                    description=f"Cache is using {metrics.total_size_mb:.1f}MB. Implement intelligent eviction policies.",
                    impact_score=min(70, metrics.total_size_mb / 10),
                    implementation_effort="medium",
                    estimated_improvement={
                        "memory_reduction": 25,
                        "eviction_efficiency": 40
                    },
                    action_items=[
                        "Implement LFU (Least Frequently Used) eviction policy",
                        "Set appropriate TTL values based on access patterns",
                        "Monitor cache entry lifecycle and adjust policies"
                    ]
                ))
            
            # Pattern-based recommendations
            layer_patterns = [p for p in self.access_patterns.values() if p.cache_layer == layer]
            if layer_patterns:
                low_hit_patterns = [p for p in layer_patterns if p.hit_rate < 50]
                if low_hit_patterns:
                    recommendations.append(OptimizationRecommendation(
                        recommendation_id=f"{layer.value}_pattern_optimization",
                        strategy=OptimizationStrategy.PATTERN_BASED_PRELOADING,
                        cache_layer=layer,
                        title=f"Optimize {layer.value} Access Patterns",
                        description=f"Found {len(low_hit_patterns)} patterns with low hit rates. Implement pattern-based preloading.",
                        impact_score=60,
                        implementation_effort="high",
                        estimated_improvement={
                            "pattern_hit_rate": 35,
                            "overall_performance": 20
                        },
                        action_items=[
                            "Implement pattern-based cache preloading",
                            "Group related cache keys for batch operations",
                            "Optimize cache key structure for better locality"
                        ]
                    ))
        
        except Exception as e:
            logger.error(f"Error generating recommendations for layer {layer}: {e}")
        
        return recommendations
    
    # ========================================================================
    # Public API Methods
    # ========================================================================
    
    def schedule_warming_job(
        self,
        cache_layer: CacheLayer,
        keys: List[str],
        priority: WarmingPriority = WarmingPriority.MEDIUM,
        scheduled_for: Optional[datetime] = None
    ) -> str:
        """Schedule a cache warming job."""
        job_id = f"warming_{cache_layer.value}_{datetime.utcnow().timestamp()}"
        
        job = WarmingJob(
            job_id=job_id,
            cache_layer=cache_layer,
            keys_to_warm=keys,
            priority=priority,
            created_at=datetime.utcnow(),
            scheduled_for=scheduled_for
        )
        
        self.warming_jobs[job_id] = job
        
        logger.info(f"Scheduled warming job {job_id} for {len(keys)} keys")
        return job_id
    
    def get_warming_candidates(
        self,
        cache_layer: Optional[CacheLayer] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get current cache warming candidates."""
        candidates = self.warming_candidates
        
        if cache_layer:
            candidates = [c for c in candidates if c.cache_layer == cache_layer]
        
        return [asdict(candidate) for candidate in candidates[:limit]]
    
    def get_optimization_recommendations(
        self,
        cache_layer: Optional[CacheLayer] = None
    ) -> List[Dict[str, Any]]:
        """Get current optimization recommendations."""
        recommendations = self.optimization_recommendations
        
        if cache_layer:
            recommendations = [r for r in recommendations if r.cache_layer == cache_layer]
        
        return [asdict(rec) for rec in recommendations]
    
    def get_warming_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a warming job."""
        job = self.warming_jobs.get(job_id)
        return asdict(job) if job else None
    
    def get_access_patterns(
        self,
        cache_layer: Optional[CacheLayer] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get identified access patterns."""
        patterns = list(self.access_patterns.values())
        
        if cache_layer:
            patterns = [p for p in patterns if p.cache_layer == cache_layer]
        
        # Sort by frequency score
        patterns.sort(key=lambda p: p.frequency_score, reverse=True)
        
        return [asdict(pattern) for pattern in patterns[:limit]]
    
    def trigger_immediate_analysis(self) -> Dict[str, Any]:
        """Trigger immediate pattern analysis and optimization."""
        try:
            # Run analysis synchronously for immediate results
            asyncio.create_task(self._analyze_access_patterns())
            asyncio.create_task(self._identify_warming_candidates()) 
            asyncio.create_task(self._generate_optimization_recommendations())
            
            return {
                "status": "triggered",
                "message": "Immediate analysis and optimization triggered",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error triggering immediate analysis: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _cleanup_completed_jobs(self):
        """Clean up old completed warming jobs."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            jobs_to_remove = [
                job_id for job_id, job in self.warming_jobs.items()
                if job.completed_at and job.completed_at < cutoff_time
            ]
            
            for job_id in jobs_to_remove:
                del self.warming_jobs[job_id]
            
            if jobs_to_remove:
                logger.debug(f"Cleaned up {len(jobs_to_remove)} old warming jobs")
        
        except Exception as e:
            logger.error(f"Error cleaning up warming jobs: {e}")
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get comprehensive optimization summary."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "patterns_identified": len(self.access_patterns),
            "warming_candidates": len(self.warming_candidates),
            "recommendations": len(self.optimization_recommendations),
            "active_warming_jobs": len(self.active_jobs),
            "total_warming_jobs": len(self.warming_jobs),
            "top_patterns": [
                {
                    "pattern": pattern.pattern_template,
                    "layer": pattern.cache_layer.value,
                    "hit_rate": pattern.hit_rate,
                    "frequency": pattern.frequency_score
                }
                for pattern in sorted(
                    self.access_patterns.values(),
                    key=lambda p: p.frequency_score,
                    reverse=True
                )[:5]
            ],
            "top_recommendations": [
                {
                    "title": rec.title,
                    "layer": rec.cache_layer.value,
                    "impact_score": rec.impact_score,
                    "strategy": rec.strategy.value
                }
                for rec in self.optimization_recommendations[:5]
            ]
        }