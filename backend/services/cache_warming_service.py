"""
Cache Warming Service with Predictive Analytics
Intelligent cache warming based on usage patterns and predictions.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .metrics_service import MetricsService

# Import our services
from .redis_cache_service import RedisCacheService
from .smart_cache_manager import AccessPattern, SmartCacheManager

logger = logging.getLogger(__name__)


# ============================================================================
# Cache Warming Configuration
# ============================================================================


class WarmingStrategy(str, Enum):
    """Cache warming strategies."""

    SCHEDULED = "scheduled"  # Time-based warming
    PREDICTIVE = "predictive"  # ML-based prediction warming
    PATTERN_BASED = "pattern_based"  # Access pattern based
    DEPENDENCY_BASED = "dependency_based"  # Based on data dependencies
    REACTIVE = "reactive"  # React to cache misses
    HYBRID = "hybrid"  # Combination of strategies


class WarmingPriority(str, Enum):
    """Priority levels for cache warming."""

    CRITICAL = "critical"  # Must warm immediately
    HIGH = "high"  # Warm soon
    MEDIUM = "medium"  # Warm when convenient
    LOW = "low"  # Warm during idle time


@dataclass
class WarmingTask:
    """A cache warming task."""

    key: str
    priority: WarmingPriority
    strategy: WarmingStrategy
    loader_func: Callable[[], Any]

    # Scheduling
    scheduled_time: datetime | None = None
    ttl: int | None = None

    # Dependencies
    dependencies: list[str] = field(default_factory=list)
    dependent_keys: list[str] = field(default_factory=list)

    # Metadata
    estimated_load_time_ms: float = 100.0
    estimated_size_bytes: int = 1024
    access_probability: float = 0.5
    user_groups: list[str] = field(default_factory=list)

    # State tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    attempts: int = 0
    last_attempt: datetime | None = None
    completed: bool = False
    error: str | None = None

    def should_execute(self, current_time: datetime) -> bool:
        """Check if task should be executed now."""
        if self.completed:
            return False

        # Check scheduling
        if self.scheduled_time and current_time < self.scheduled_time:
            return False

        # Check attempt limits and backoff
        if self.attempts >= 3:
            return False

        # Exponential backoff on retries
        if self.last_attempt:
            backoff_minutes = 2**self.attempts  # 2, 4, 8 minutes
            backoff_time = self.last_attempt + timedelta(minutes=backoff_minutes)
            if current_time < backoff_time:
                return False

        return True

    def get_execution_order(self) -> int:
        """Get execution order (lower = higher priority)."""
        priority_order = {
            WarmingPriority.CRITICAL: 0,
            WarmingPriority.HIGH: 100,
            WarmingPriority.MEDIUM: 200,
            WarmingPriority.LOW: 300,
        }

        base_order = priority_order[self.priority]

        # Adjust by access probability
        probability_bonus = int((1.0 - self.access_probability) * 50)

        # Adjust by estimated load time (faster loads first)
        time_bonus = int(self.estimated_load_time_ms / 10)

        return base_order + probability_bonus + time_bonus


@dataclass
class WarmingStatistics:
    """Statistics for cache warming operations."""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cache_hit_improvement: float = 0.0
    average_warm_time_ms: float = 0.0
    total_bytes_warmed: int = 0

    # Strategy effectiveness
    strategy_success_rates: dict[str, float] = field(default_factory=dict)
    strategy_performance: dict[str, float] = field(default_factory=dict)

    # Time-based analysis
    hourly_effectiveness: dict[int, float] = field(default_factory=dict)

    def update_completion(self, task: WarmingTask, success: bool, duration_ms: float):
        """Update statistics with task completion."""
        self.total_tasks += 1

        if success:
            self.completed_tasks += 1
            self.total_bytes_warmed += task.estimated_size_bytes

            # Update average warm time
            self.average_warm_time_ms = (
                self.average_warm_time_ms * (self.completed_tasks - 1) + duration_ms
            ) / self.completed_tasks
        else:
            self.failed_tasks += 1

        # Update strategy statistics
        strategy_name = task.strategy.value
        if strategy_name not in self.strategy_success_rates:
            self.strategy_success_rates[strategy_name] = 0.0
            self.strategy_performance[strategy_name] = 0.0

        # Simple moving average for success rate
        current_rate = self.strategy_success_rates[strategy_name]
        self.strategy_success_rates[strategy_name] = (
            current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
        )

        # Performance metric (lower is better)
        if success:
            current_perf = self.strategy_performance[strategy_name]
            self.strategy_performance[strategy_name] = (
                current_perf * 0.9 + duration_ms * 0.1
            )


# ============================================================================
# Cache Warming Service
# ============================================================================


class CacheWarmingService:
    """
    Intelligent cache warming service with predictive analytics.
    """

    def __init__(
        self,
        redis_cache: RedisCacheService,
        smart_cache: SmartCacheManager | None = None,
        metrics_service: MetricsService | None = None,
    ):
        """Initialize cache warming service."""
        self.redis_cache = redis_cache
        self.smart_cache = smart_cache
        self.metrics_service = metrics_service

        # Task management
        self.warming_tasks: dict[str, WarmingTask] = {}
        self.task_queue: list[WarmingTask] = []
        self.completed_tasks: deque = deque(maxlen=1000)

        # Statistics
        self.stats = WarmingStatistics()

        # Loader registry
        self.data_loaders: dict[str, Callable] = {}

        # Background processing
        self.is_running = False
        self.worker_tasks: list[asyncio.Task] = []
        self.max_workers = 3

        # Configuration
        self.config = {
            "max_queue_size": 1000,
            "worker_delay_ms": 100,
            "batch_size": 10,
            "prediction_window_hours": 24,
            "warming_threshold_probability": 0.3,
            "max_warming_time_minutes": 30,
        }

        logger.info("Cache Warming Service initialized")

    # ========================================================================
    # Data Loader Registration
    # ========================================================================

    def register_loader(self, pattern: str, loader_func: Callable):
        """Register a data loader for a key pattern."""
        self.data_loaders[pattern] = loader_func
        logger.info(f"Registered data loader for pattern: {pattern}")

    def get_loader(self, key: str) -> Callable | None:
        """Get appropriate loader for a key."""
        # Find matching pattern
        for pattern, loader in self.data_loaders.items():
            if self._match_pattern(key, pattern):
                return loader
        return None

    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern (simple glob-like matching)."""
        if "*" not in pattern:
            return key == pattern

        # Simple wildcard matching
        pattern_parts = pattern.split("*")
        if not pattern_parts:
            return True

        # Check if key starts and ends with the pattern parts
        if pattern_parts[0] and not key.startswith(pattern_parts[0]):
            return False
        if pattern_parts[-1] and not key.endswith(pattern_parts[-1]):
            return False

        return True

    # ========================================================================
    # Task Management
    # ========================================================================

    def add_warming_task(
        self,
        key: str,
        priority: WarmingPriority = WarmingPriority.MEDIUM,
        strategy: WarmingStrategy = WarmingStrategy.PREDICTIVE,
        loader_func: Callable | None = None,
        scheduled_time: datetime | None = None,
        ttl: int | None = None,
        dependencies: list[str] | None = None,
        user_groups: list[str] | None = None,
        estimated_load_time_ms: float = 100.0,
        estimated_size_bytes: int = 1024,
    ) -> bool:
        """Add a cache warming task."""
        # Check if key already exists in cache
        if self.redis_cache.exists(key):
            logger.debug(f"Key {key} already in cache, skipping warming")
            return False

        # Get loader function
        if not loader_func:
            loader_func = self.get_loader(key)
            if not loader_func:
                logger.warning(f"No loader function found for key: {key}")
                return False

        # Create task
        task = WarmingTask(
            key=key,
            priority=priority,
            strategy=strategy,
            loader_func=loader_func,
            scheduled_time=scheduled_time,
            ttl=ttl,
            dependencies=dependencies or [],
            user_groups=user_groups or [],
            estimated_load_time_ms=estimated_load_time_ms,
            estimated_size_bytes=estimated_size_bytes,
        )

        # Estimate access probability if smart cache is available
        if self.smart_cache:
            profile = self.smart_cache.key_profiles.get(key)
            if profile:
                task.access_probability = profile.access_probability_score

        # Add to queue
        self.warming_tasks[key] = task
        self._enqueue_task(task)

        logger.debug(f"Added warming task for key: {key} (priority: {priority})")
        return True

    def _enqueue_task(self, task: WarmingTask):
        """Add task to execution queue with proper ordering."""
        # Check queue size limit
        if len(self.task_queue) >= self.config["max_queue_size"]:
            # Remove lowest priority tasks
            self.task_queue.sort(key=lambda t: t.get_execution_order())
            self.task_queue = self.task_queue[: self.config["max_queue_size"] - 1]

        self.task_queue.append(task)

        # Sort queue by execution order
        self.task_queue.sort(key=lambda t: t.get_execution_order())

    def remove_warming_task(self, key: str) -> bool:
        """Remove a warming task."""
        if key in self.warming_tasks:
            # Remove from active queue
            self.task_queue = [t for t in self.task_queue if t.key != key]

            # Remove from tasks dict
            del self.warming_tasks[key]

            logger.debug(f"Removed warming task for key: {key}")
            return True

        return False

    # ========================================================================
    # Predictive Warming
    # ========================================================================

    async def predict_and_schedule_warming(self):
        """Predict which keys should be warmed and schedule tasks."""
        if not self.smart_cache:
            logger.info("Smart cache not available for predictive warming")
            return

        _ = datetime.utcnow() + timedelta(hours=self.config["prediction_window_hours"])

        # Analyze access patterns for prediction
        predictions = await self._analyze_access_patterns()

        # Schedule warming tasks for high-probability keys
        for key, probability in predictions.items():
            if probability >= self.config["warming_threshold_probability"]:
                if key not in self.warming_tasks and not self.redis_cache.exists(key):

                    # Determine priority based on probability
                    if probability >= 0.8:
                        priority = WarmingPriority.HIGH
                    elif probability >= 0.5:
                        priority = WarmingPriority.MEDIUM
                    else:
                        priority = WarmingPriority.LOW

                    # Schedule for near future
                    schedule_time = datetime.utcnow() + timedelta(minutes=5)

                    self.add_warming_task(
                        key=key,
                        priority=priority,
                        strategy=WarmingStrategy.PREDICTIVE,
                        scheduled_time=schedule_time,
                    )

        logger.info(
            f"Scheduled {len([p for p in predictions.values() if p >= self.config['warming_threshold_probability']])} predictive warming tasks"
        )

    async def _analyze_access_patterns(self) -> dict[str, float]:
        """Analyze access patterns to predict future cache needs."""
        predictions = {}

        if not self.smart_cache:
            return predictions

        current_time = datetime.utcnow()

        # Analyze each key profile for prediction
        for key, profile in self.smart_cache.key_profiles.items():
            # Skip if already in cache
            if self.redis_cache.exists(key):
                continue

            probability = 0.0

            # Base probability from ML model
            if profile.access_probability_score > 0:
                probability = profile.access_probability_score

            # Pattern-based adjustments
            if profile.access_pattern == AccessPattern.HOTSPOT:
                probability += 0.2  # Hot keys likely to be accessed again
            elif profile.access_pattern == AccessPattern.TEMPORAL:
                # Check if we're in a typical access time window
                if self._in_typical_access_window(profile, current_time):
                    probability += 0.3
            elif profile.access_pattern == AccessPattern.SEASONAL:
                # Seasonal pattern prediction
                if self._predict_seasonal_access(profile, current_time):
                    probability += 0.25

            # Frequency and recency adjustments
            probability += min(profile.frequency_score * 0.1, 0.2)
            probability += profile.recency_score * 0.1

            # Clamp probability
            probability = max(0.0, min(1.0, probability))

            if probability > 0.1:  # Only consider keys with some probability
                predictions[key] = probability

        return predictions

    def _in_typical_access_window(self, profile, current_time: datetime) -> bool:
        """Check if current time is in typical access window for temporal patterns."""
        if not profile.access_times:
            return False

        # Get hour distribution
        hours = [t.hour for t in profile.access_times]
        current_hour = current_time.hour

        # Check if current hour is common for this key
        hour_counts = defaultdict(int)
        for hour in hours:
            hour_counts[hour] += 1

        total_accesses = len(hours)
        current_hour_ratio = hour_counts[current_hour] / total_accesses

        return current_hour_ratio > 0.2  # More than 20% of accesses in this hour

    def _predict_seasonal_access(self, profile, current_time: datetime) -> bool:
        """Predict if seasonal pattern indicates access is likely."""
        # Simple implementation - would be more sophisticated in production
        if profile.seasonality_score > 0.7:  # High seasonality
            # Check day-of-week pattern
            if profile.access_times:
                days = [t.weekday() for t in profile.access_times]
                current_day = current_time.weekday()

                day_counts = defaultdict(int)
                for day in days:
                    day_counts[day] += 1

                total_accesses = len(days)
                current_day_ratio = day_counts[current_day] / total_accesses

                return current_day_ratio > 0.3  # More than 30% of accesses on this day

        return False

    # ========================================================================
    # Pattern-based Warming
    # ========================================================================

    async def schedule_pattern_based_warming(self):
        """Schedule warming based on detected access patterns."""
        if not self.smart_cache:
            return

        # Group keys by access patterns
        pattern_groups = defaultdict(list)
        for key, profile in self.smart_cache.key_profiles.items():
            if not self.redis_cache.exists(key):
                pattern_groups[profile.access_pattern].append((key, profile))

        # Schedule warming based on patterns
        for pattern, keys in pattern_groups.items():
            await self._schedule_pattern_group(pattern, keys)

    async def _schedule_pattern_group(
        self, pattern: AccessPattern, keys: list[tuple[str, Any]]
    ):
        """Schedule warming for a group of keys with the same pattern."""
        if pattern == AccessPattern.HOTSPOT:
            # Warm hotspot keys with high priority
            for key, profile in keys[:10]:  # Top 10 hotspot keys
                if profile.frequency_score > 1.0:  # High frequency
                    self.add_warming_task(
                        key=key,
                        priority=WarmingPriority.HIGH,
                        strategy=WarmingStrategy.PATTERN_BASED,
                    )

        elif pattern == AccessPattern.TEMPORAL:
            # Warm temporal keys during their typical access windows
            for key, profile in keys:
                if self._in_typical_access_window(profile, datetime.utcnow()):
                    self.add_warming_task(
                        key=key,
                        priority=WarmingPriority.MEDIUM,
                        strategy=WarmingStrategy.PATTERN_BASED,
                        scheduled_time=datetime.utcnow() + timedelta(minutes=2),
                    )

        elif pattern == AccessPattern.SEQUENTIAL:
            # Warm sequential keys in batches
            sorted_keys = sorted(keys, key=lambda x: x[0])  # Sort by key name
            for i, (key, profile) in enumerate(sorted_keys[:5]):  # Batch of 5
                self.add_warming_task(
                    key=key,
                    priority=WarmingPriority.LOW,
                    strategy=WarmingStrategy.PATTERN_BASED,
                    scheduled_time=datetime.utcnow() + timedelta(minutes=i),
                )

    # ========================================================================
    # Reactive Warming
    # ========================================================================

    async def handle_cache_miss(self, key: str, user_id: str | None = None):
        """Handle cache miss with reactive warming."""
        # Add immediate warming task for missed key
        self.add_warming_task(
            key=key,
            priority=WarmingPriority.CRITICAL,
            strategy=WarmingStrategy.REACTIVE,
        )

        # Look for related keys that might also be accessed
        related_keys = await self._find_related_keys(key)

        for related_key in related_keys:
            if (
                not self.redis_cache.exists(related_key)
                and related_key not in self.warming_tasks
            ):
                self.add_warming_task(
                    key=related_key,
                    priority=WarmingPriority.HIGH,
                    strategy=WarmingStrategy.REACTIVE,
                    scheduled_time=datetime.utcnow() + timedelta(seconds=30),
                )

        logger.info(
            f"Reactive warming triggered for {key} and {len(related_keys)} related keys"
        )

    async def _find_related_keys(self, key: str) -> list[str]:
        """Find keys related to the given key."""
        related_keys = []

        if not self.smart_cache:
            return related_keys

        # Find keys with similar patterns or common prefixes
        key_prefix = (
            key.split(":")[0]
            if ":" in key
            else key[: key.rfind("_")] if "_" in key else key
        )

        for other_key, profile in self.smart_cache.key_profiles.items():
            if other_key == key:
                continue

            # Check prefix similarity
            if other_key.startswith(key_prefix):
                related_keys.append(other_key)

            # Limit to prevent excessive warming
            if len(related_keys) >= 5:
                break

        return related_keys

    # ========================================================================
    # Task Execution
    # ========================================================================

    async def start_warming_workers(self):
        """Start background workers for cache warming."""
        if self.is_running:
            return

        self.is_running = True

        # Start worker tasks
        for i in range(self.max_workers):
            task = asyncio.create_task(self._warming_worker(f"worker-{i}"))
            self.worker_tasks.append(task)

        logger.info(f"Started {self.max_workers} cache warming workers")

    async def stop_warming_workers(self):
        """Stop background workers."""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel all worker tasks
        for task in self.worker_tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()

        logger.info("Stopped cache warming workers")

    async def _warming_worker(self, worker_id: str):
        """Background worker for processing warming tasks."""
        logger.info(f"Cache warming worker {worker_id} started")

        while self.is_running:
            try:
                # Get next task
                task = await self._get_next_task()

                if not task:
                    await asyncio.sleep(self.config["worker_delay_ms"] / 1000)
                    continue

                # Execute task
                await self._execute_warming_task(task, worker_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in warming worker {worker_id}: {e}")
                await asyncio.sleep(1)

        logger.info(f"Cache warming worker {worker_id} stopped")

    async def _get_next_task(self) -> WarmingTask | None:
        """Get the next task to execute."""
        if not self.task_queue:
            return None

        current_time = datetime.utcnow()

        # Find the first executable task
        for i, task in enumerate(self.task_queue):
            if task.should_execute(current_time):
                # Remove from queue
                return self.task_queue.pop(i)

        return None

    async def _execute_warming_task(self, task: WarmingTask, worker_id: str):
        """Execute a single warming task."""
        start_time = time.time()

        try:
            task.attempts += 1
            task.last_attempt = datetime.utcnow()

            logger.debug(
                f"Worker {worker_id} executing warming task for key: {task.key}"
            )

            # Load data
            if asyncio.iscoroutinefunction(task.loader_func):
                data = await task.loader_func()
            else:
                data = await asyncio.to_thread(task.loader_func)

            # Store in cache
            success = self.redis_cache.set(task.key, data, ttl=task.ttl)

            if success:
                task.completed = True
                duration_ms = (time.time() - start_time) * 1000

                # Update statistics
                self.stats.update_completion(task, True, duration_ms)

                # Move to completed tasks
                self.completed_tasks.append(task)

                # Report metrics
                if self.metrics_service:
                    self.metrics_service.record_cache_operation(
                        operation="warm",
                        cache_type="redis",
                        hit=True,
                        duration=duration_ms / 1000,
                    )

                logger.debug(
                    f"Successfully warmed cache for key: {task.key} in {duration_ms:.1f}ms"
                )
            else:
                raise Exception("Failed to store data in cache")

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            task.error = str(e)

            # Update statistics
            self.stats.update_completion(task, False, duration_ms)

            # Re-queue if not too many attempts
            if task.attempts < 3:
                self._enqueue_task(task)
            else:
                logger.error(f"Warming task failed permanently for key {task.key}: {e}")

            logger.warning(f"Warming task failed for key {task.key}: {e}")

        finally:
            # Clean up from active tasks
            if task.key in self.warming_tasks:
                if task.completed or task.attempts >= 3:
                    del self.warming_tasks[task.key]

    # ========================================================================
    # Scheduled Warming
    # ========================================================================

    async def schedule_periodic_warming(self):
        """Schedule periodic warming based on time patterns."""
        current_time = datetime.utcnow()

        # Morning warm-up (prepare for business hours)
        if current_time.hour == 7:  # 7 AM
            await self._schedule_business_hours_warming()

        # Lunch time preparation
        elif current_time.hour == 11:  # 11 AM
            await self._schedule_lunch_time_warming()

        # End of day preparation
        elif current_time.hour == 17:  # 5 PM
            await self._schedule_evening_warming()

    async def _schedule_business_hours_warming(self):
        """Schedule warming for business hours."""
        if not self.smart_cache:
            return

        # Find keys commonly accessed during business hours (9-17)
        business_hour_keys = []

        for key, profile in self.smart_cache.key_profiles.items():
            if not self.redis_cache.exists(key):
                # Check if key is commonly accessed during business hours
                if profile.access_times:
                    business_accesses = [
                        t for t in profile.access_times if 9 <= t.hour <= 17
                    ]

                    business_ratio = len(business_accesses) / len(profile.access_times)

                    if business_ratio > 0.6:  # 60% of accesses during business hours
                        business_hour_keys.append(key)

        # Schedule warming
        for key in business_hour_keys[:20]:  # Limit to top 20
            self.add_warming_task(
                key=key,
                priority=WarmingPriority.MEDIUM,
                strategy=WarmingStrategy.SCHEDULED,
                scheduled_time=datetime.utcnow() + timedelta(minutes=30),
            )

        logger.info(
            f"Scheduled {len(business_hour_keys)} keys for business hours warming"
        )

    async def _schedule_lunch_time_warming(self):
        """Schedule warming for lunch time patterns."""
        # Similar logic for lunch time patterns
        pass

    async def _schedule_evening_warming(self):
        """Schedule warming for evening patterns."""
        # Similar logic for evening patterns
        pass

    # ========================================================================
    # API and Monitoring
    # ========================================================================

    def get_warming_status(self) -> dict[str, Any]:
        """Get current warming status."""
        return {
            "is_running": self.is_running,
            "active_workers": len(self.worker_tasks),
            "queue_size": len(self.task_queue),
            "active_tasks": len(self.warming_tasks),
            "completed_tasks": len(self.completed_tasks),
            "statistics": {
                "total_tasks": self.stats.total_tasks,
                "completed_tasks": self.stats.completed_tasks,
                "failed_tasks": self.stats.failed_tasks,
                "success_rate": (
                    (self.stats.completed_tasks / self.stats.total_tasks * 100)
                    if self.stats.total_tasks > 0
                    else 0
                ),
                "average_warm_time_ms": self.stats.average_warm_time_ms,
                "total_bytes_warmed": self.stats.total_bytes_warmed,
            },
            "strategy_performance": dict(self.stats.strategy_success_rates),
            "current_tasks": [
                {
                    "key": task.key,
                    "priority": task.priority.value,
                    "strategy": task.strategy.value,
                    "attempts": task.attempts,
                    "scheduled_time": (
                        task.scheduled_time.isoformat() if task.scheduled_time else None
                    ),
                }
                for task in list(self.task_queue)[:10]  # Top 10 tasks
            ],
        }

    def get_warming_recommendations(self) -> list[dict[str, Any]]:
        """Get recommendations for warming optimization."""
        recommendations = []

        # Analyze strategy performance
        if self.stats.strategy_success_rates:
            best_strategy = max(
                self.stats.strategy_success_rates.items(), key=lambda x: x[1]
            )
            worst_strategy = min(
                self.stats.strategy_success_rates.items(), key=lambda x: x[1]
            )

            if best_strategy[1] > 0.8:
                recommendations.append(
                    {
                        "type": "strategy_optimization",
                        "message": f"Strategy '{best_strategy[0]}' has high success rate ({best_strategy[1]:.1%}). Consider using it more.",
                        "priority": "medium",
                    }
                )

            if worst_strategy[1] < 0.5:
                recommendations.append(
                    {
                        "type": "strategy_optimization",
                        "message": f"Strategy '{worst_strategy[0]}' has low success rate ({worst_strategy[1]:.1%}). Consider tuning or reducing usage.",
                        "priority": "high",
                    }
                )

        # Queue size recommendations
        if len(self.task_queue) > self.config["max_queue_size"] * 0.8:
            recommendations.append(
                {
                    "type": "capacity",
                    "message": "Warming queue is near capacity. Consider increasing workers or reducing task frequency.",
                    "priority": "high",
                }
            )

        # Performance recommendations
        if self.stats.average_warm_time_ms > 5000:  # 5 seconds
            recommendations.append(
                {
                    "type": "performance",
                    "message": f"Average warming time is high ({self.stats.average_warm_time_ms:.0f}ms). Consider optimizing data loaders.",
                    "priority": "medium",
                }
            )

        return recommendations


if __name__ == "__main__":
    # Example usage
    async def main():
        from .redis_cache_service import RedisCacheService, RedisConfig

        # Create services
        redis_config = RedisConfig()
        redis_cache = RedisCacheService(redis_config)
        warming_service = CacheWarmingService(redis_cache)

        # Register a simple loader
        def load_user_data(user_id: str):
            return {"id": user_id, "name": f"User {user_id}", "data": "sample"}

        warming_service.register_loader("user:*", lambda: load_user_data("123"))

        # Add some warming tasks
        warming_service.add_warming_task(
            "user:123",
            priority=WarmingPriority.HIGH,
            strategy=WarmingStrategy.PREDICTIVE,
        )

        # Start workers
        await warming_service.start_warming_workers()

        # Let it run for a bit
        await asyncio.sleep(5)

        # Check status
        status = warming_service.get_warming_status()
        print(f"Warming status: {status}")

        # Stop workers
        await warming_service.stop_warming_workers()

    # Run example
    # asyncio.run(main())
