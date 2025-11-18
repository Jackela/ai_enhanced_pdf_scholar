"""
Smart Cache Manager with ML-driven Optimization
Intelligent caching strategies using machine learning for access pattern prediction.
"""

import asyncio
import contextlib
import hashlib
import json
import logging
import pickle
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import numpy as np

try:
    from sklearn.cluster import KMeans
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
    SKLEARN_IMPORT_ERROR: Exception | None = None
except Exception as import_error:  # pragma: no cover - optional dependency
    KMeans = None  # type: ignore[assignment]
    RandomForestRegressor = None  # type: ignore[assignment]
    StandardScaler = None  # type: ignore[assignment]
    SKLEARN_AVAILABLE = False
    SKLEARN_IMPORT_ERROR = import_error

from .metrics_service import MetricsService

# Import our services
from .redis_cache_service import RedisCacheService

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes for ML-driven Caching
# ============================================================================


class AccessPattern(str, Enum):
    """Types of access patterns."""

    SEQUENTIAL = "sequential"
    RANDOM = "random"
    HOTSPOT = "hotspot"
    TEMPORAL = "temporal"
    SEASONAL = "seasonal"


class CacheStrategy(str, Enum):
    """Cache replacement strategies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    ARC = "arc"  # Adaptive Replacement Cache
    SLRU = "slru"  # Segmented LRU
    ML_PREDICT = "ml_predict"  # ML-predicted replacement


@dataclass
class AccessRecord:
    """Record of a cache access event."""

    key: str
    timestamp: datetime
    hit: bool
    user_id: str | None = None
    session_id: str | None = None
    request_type: str | None = None
    response_size: int = 0
    processing_time_ms: float = 0.0

    def to_feature_vector(self) -> list[float]:
        """Convert to ML feature vector."""
        hour_of_day = self.timestamp.hour
        day_of_week = self.timestamp.weekday()

        features = [
            hour_of_day / 24.0,  # Normalized hour
            day_of_week / 7.0,  # Normalized day of week
            self.response_size / 1024.0,  # Size in KB
            self.processing_time_ms / 1000.0,  # Time in seconds
            1.0 if self.hit else 0.0,  # Hit indicator
        ]

        # Add hash-based features for key
        key_hash = int(hashlib.sha256(self.key.encode()).hexdigest()[:8], 16)
        features.append((key_hash % 1000) / 1000.0)  # Key hash feature

        return features


@dataclass
class CacheKeyProfile:
    """Profile of a cache key's access patterns."""

    key: str
    first_access: datetime
    last_access: datetime
    access_count: int = 0
    hit_count: int = 0
    miss_count: int = 0

    # Access timing
    access_times: deque = field(default_factory=lambda: deque(maxlen=100))
    inter_arrival_times: list[float] = field(default_factory=list)

    # Size and performance
    avg_response_size: float = 0.0
    avg_processing_time: float = 0.0

    # Pattern analysis
    access_pattern: AccessPattern = AccessPattern.RANDOM
    seasonality_score: float = 0.0
    frequency_score: float = 0.0
    recency_score: float = 0.0

    # ML predictions
    predicted_next_access: datetime | None = None
    access_probability_score: float = 0.0

    def update_access(
        self,
        access_time: datetime,
        hit: bool,
        response_size: int = 0,
        processing_time: float = 0.0,
    ) -> None:
        """Update profile with new access."""
        # Update counters
        self.access_count += 1
        if hit:
            self.hit_count += 1
        else:
            self.miss_count += 1

        # Update timing
        if self.access_times:
            interval = (access_time - self.last_access).total_seconds()
            self.inter_arrival_times.append(interval)
            if len(self.inter_arrival_times) > 50:  # Keep recent history
                self.inter_arrival_times = self.inter_arrival_times[-50:]

        self.access_times.append(access_time)
        self.last_access = access_time

        # Update averages
        self.avg_response_size = (
            self.avg_response_size * (self.access_count - 1) + response_size
        ) / self.access_count
        self.avg_processing_time = (
            self.avg_processing_time * (self.access_count - 1) + processing_time
        ) / self.access_count

    def calculate_scores(self) -> None:
        """Calculate various scoring metrics."""
        now = datetime.utcnow()

        # Recency score (higher for recent access)
        time_since_access = (now - self.last_access).total_seconds()
        self.recency_score = 1.0 / (1.0 + time_since_access / 3600)  # Decay over hours

        # Frequency score
        total_time = (self.last_access - self.first_access).total_seconds()
        if total_time > 0:
            self.frequency_score = self.access_count / (
                total_time / 3600
            )  # Accesses per hour

        # Pattern detection
        self._detect_access_pattern()

    def _detect_access_pattern(self) -> None:
        """Detect access pattern from historical data."""
        if len(self.inter_arrival_times) < 5:
            return

        intervals = np.array(self.inter_arrival_times)

        # Calculate coefficient of variation
        if len(intervals) > 1:
            cv = (
                np.std(intervals) / np.mean(intervals)
                if np.mean(intervals) > 0
                else float("inf")
            )

            # Pattern classification based on interval regularity
            if cv < 0.3:  # Low variation - regular access
                if np.mean(intervals) < 300:  # Within 5 minutes
                    self.access_pattern = AccessPattern.HOTSPOT
                else:
                    self.access_pattern = AccessPattern.TEMPORAL
            elif cv > 2.0:  # High variation
                self.access_pattern = AccessPattern.RANDOM
            else:
                self.access_pattern = AccessPattern.SEQUENTIAL

        # Seasonality detection (simple hour-of-day analysis)
        if len(self.access_times) >= 20:
            hours = [t.hour for t in self.access_times]
            hour_counts = np.bincount(hours, minlength=24)

            # Calculate entropy as inverse seasonality measure
            hour_probs = hour_counts / np.sum(hour_counts)
            hour_probs = hour_probs[hour_probs > 0]  # Remove zeros for log
            entropy = -np.sum(hour_probs * np.log2(hour_probs))

            # Seasonality score (0 = very seasonal, 1 = uniform)
            max_entropy = np.log2(24)  # Maximum possible entropy
            self.seasonality_score = 1.0 - (entropy / max_entropy)


# ============================================================================
# ML Models for Cache Prediction
# ============================================================================


class CacheMLPredictor:
    """Machine learning predictor for cache access patterns."""

    def __init__(self) -> None:
        """Initialize ML models."""
        self.ml_enabled = SKLEARN_AVAILABLE
        self.access_predictor: RandomForestRegressor | None = None
        self.key_clusterer: KMeans | None = None
        self.feature_scaler: StandardScaler | None = None

        if self.ml_enabled:
            # Access probability predictor
            self.access_predictor = RandomForestRegressor(
                n_estimators=50, max_depth=10, random_state=42
            )

            # Key clustering for pattern recognition
            self.key_clusterer = KMeans(n_clusters=10, random_state=42)
            self.feature_scaler = StandardScaler()
        else:
            logger.warning(
                "scikit-learn is not installed; disabling ML-driven cache optimizations. "
                "Install scikit-learn to enable predictive caching."
            )
            if SKLEARN_IMPORT_ERROR:
                logger.debug("Smart cache ML import error: %s", SKLEARN_IMPORT_ERROR)

        # Training data
        self.training_data: list[tuple[list[float], float]] = []
        self.is_trained = False
        self.last_training = None
        self.training_interval_hours = 6  # Retrain every 6 hours

        if self.ml_enabled:
            logger.info("Cache ML Predictor initialized (scikit-learn backend)")

    def add_training_sample(
        self, access_record: AccessRecord, key_profile: CacheKeyProfile
    ) -> None:
        """Add a training sample for the ML model."""
        if not self.ml_enabled:
            return

        # Create feature vector
        features = access_record.to_feature_vector()

        # Add key profile features
        features.extend(
            [
                key_profile.frequency_score,
                key_profile.recency_score,
                key_profile.seasonality_score,
                key_profile.avg_response_size / 1024.0,
                key_profile.avg_processing_time / 1000.0,
            ]
        )

        # Target: probability of future access (1.0 for hit, 0.0 for miss)
        target = 1.0 if access_record.hit else 0.0

        self.training_data.append((features, target))

        # Limit training data size
        if len(self.training_data) > 10000:
            self.training_data = self.training_data[-5000:]  # Keep recent half

    async def train_models(self) -> Any:
        """Train ML models with collected data."""
        if not self.ml_enabled:
            return False

        if len(self.training_data) < 100:
            logger.info("Insufficient training data for ML models")
            return False

        try:
            # Prepare training data
            X = np.array([sample[0] for sample in self.training_data])
            y = np.array([sample[1] for sample in self.training_data])

            # Scale features
            X_scaled = self.feature_scaler.fit_transform(X)

            # Train access predictor
            await asyncio.to_thread(self.access_predictor.fit, X_scaled, y)

            # Train key clusterer
            await asyncio.to_thread(self.key_clusterer.fit, X_scaled)

            self.is_trained = True
            self.last_training = datetime.utcnow()

            logger.info(f"ML models trained with {len(self.training_data)} samples")
            return True

        except Exception as e:
            logger.error(f"Failed to train ML models: {e}")
            return False

    def predict_access_probability(
        self, access_record: AccessRecord, key_profile: CacheKeyProfile
    ) -> float:
        """Predict probability of future access for a key."""
        if not self.ml_enabled or not self.is_trained:
            return 0.5  # Default probability

        try:
            # Create feature vector
            features = access_record.to_feature_vector()
            features.extend(
                [
                    key_profile.frequency_score,
                    key_profile.recency_score,
                    key_profile.seasonality_score,
                    key_profile.avg_response_size / 1024.0,
                    key_profile.avg_processing_time / 1000.0,
                ]
            )

            # Scale features
            X = np.array([features])
            X_scaled = self.feature_scaler.transform(X)

            # Predict
            probability = self.access_predictor.predict(X_scaled)[0]
            return max(0.0, min(1.0, probability))  # Clamp to [0, 1]

        except Exception as e:
            logger.error(f"Error predicting access probability: {e}")
            return 0.5

    def get_key_cluster(
        self, access_record: AccessRecord, key_profile: CacheKeyProfile
    ) -> int:
        """Get cluster ID for a key based on its features."""
        if not self.ml_enabled or not self.is_trained:
            return 0

        try:
            features = access_record.to_feature_vector()
            features.extend(
                [
                    key_profile.frequency_score,
                    key_profile.recency_score,
                    key_profile.seasonality_score,
                    key_profile.avg_response_size / 1024.0,
                    key_profile.avg_processing_time / 1000.0,
                ]
            )

            X = np.array([features])
            X_scaled = self.feature_scaler.transform(X)

            cluster = self.key_clusterer.predict(X_scaled)[0]
            return int(cluster)

        except Exception as e:
            logger.error(f"Error getting key cluster: {e}")
            return 0

    def needs_retraining(self) -> bool:
        """Check if models need retraining."""
        if not self.ml_enabled:
            return False

        if not self.is_trained:
            return len(self.training_data) >= 100

        if not self.last_training:
            return True

        hours_since_training = (
            datetime.utcnow() - self.last_training
        ).total_seconds() / 3600
        return hours_since_training >= self.training_interval_hours


# ============================================================================
# Smart Cache Manager
# ============================================================================


class SmartCacheManager:
    """
    Intelligent cache manager using ML for optimization.
    """

    def __init__(
        self,
        redis_cache: RedisCacheService,
        metrics_service: MetricsService | None = None,
    ) -> None:
        """Initialize smart cache manager."""
        self.redis_cache = redis_cache
        self.metrics_service = metrics_service

        # ML predictor
        self.ml_predictor = CacheMLPredictor()

        # Key profiles and access tracking
        self.key_profiles: dict[str, CacheKeyProfile] = {}
        self.access_history: deque = deque(maxlen=10000)

        # Cache strategy configuration
        self.default_strategy = CacheStrategy.ML_PREDICT
        self.strategy_by_pattern: dict[AccessPattern, CacheStrategy] = {
            AccessPattern.HOTSPOT: CacheStrategy.LFU,
            AccessPattern.TEMPORAL: CacheStrategy.LRU,
            AccessPattern.SEQUENTIAL: CacheStrategy.SLRU,
            AccessPattern.RANDOM: CacheStrategy.ARC,
            AccessPattern.SEASONAL: CacheStrategy.ML_PREDICT,
        }

        # Performance tracking
        self.performance_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "ml_predictions_made": 0,
            "ml_prediction_accuracy": 0.0,
            "eviction_decisions": 0,
            "prefetch_actions": 0,
        }

        # Background tasks
        self.optimization_task: asyncio.Task | None = None
        self.is_optimizing = False

        logger.info("Smart Cache Manager initialized")

    # ========================================================================
    # Core Cache Operations with Intelligence
    # ========================================================================

    async def get(
        self,
        key: str,
        default: Any = None,
        user_id: str | None = None,
        session_id: str | None = None,
        request_type: str | None = None,
    ) -> Any:
        """Intelligent cache get with access tracking."""
        start_time = time.time()

        # Get from cache
        value = self.redis_cache.get(key, default)
        hit = value != default

        processing_time = (time.time() - start_time) * 1000  # ms

        # Record access
        access_record = AccessRecord(
            key=key,
            timestamp=datetime.utcnow(),
            hit=hit,
            user_id=user_id,
            session_id=session_id,
            request_type=request_type,
            processing_time_ms=processing_time,
        )

        await self._record_access(access_record)

        # Update performance stats
        self.performance_stats["total_requests"] += 1
        if hit:
            self.performance_stats["cache_hits"] += 1
        else:
            self.performance_stats["cache_misses"] += 1

        # Trigger intelligent prefetching
        if hit:
            await self._intelligent_prefetch(key, access_record)

        return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        user_id: str | None = None,
        force_eviction: bool = False,
    ) -> bool:
        """Intelligent cache set with ML-driven TTL optimization."""
        # Get or create key profile
        profile = self.key_profiles.get(key)
        if not profile:
            profile = CacheKeyProfile(
                key=key, first_access=datetime.utcnow(), last_access=datetime.utcnow()
            )
            self.key_profiles[key] = profile

        # Optimize TTL using ML predictions
        if ttl is None:
            ttl = await self._predict_optimal_ttl(key, profile)

        # Check if eviction is needed
        if force_eviction or await self._should_evict_for_space():
            await self._intelligent_eviction()

        # Store in cache
        response_size = len(pickle.dumps(value)) if value else 0
        success = self.redis_cache.set(key, value, ttl=ttl)

        # Record access for ML training
        access_record = AccessRecord(
            key=key,
            timestamp=datetime.utcnow(),
            hit=False,  # Set operation is always a miss
            user_id=user_id,
            response_size=response_size,
        )

        await self._record_access(access_record)

        return success

    async def delete(self, *keys: str) -> int:
        """Delete keys with profile cleanup."""
        deleted = self.redis_cache.delete(*keys)

        # Clean up profiles
        for key in keys:
            self.key_profiles.pop(key, None)

        return deleted

    # ========================================================================
    # Access Tracking and Analysis
    # ========================================================================

    async def _record_access(self, access_record: AccessRecord) -> None:
        """Record access for ML training and analysis."""
        self.access_history.append(access_record)

        # Update key profile
        profile = self.key_profiles.get(access_record.key)
        if not profile:
            profile = CacheKeyProfile(
                key=access_record.key,
                first_access=access_record.timestamp,
                last_access=access_record.timestamp,
            )
            self.key_profiles[access_record.key] = profile

        profile.update_access(
            access_record.timestamp,
            access_record.hit,
            access_record.response_size,
            access_record.processing_time_ms,
        )

        # Update profile scores
        profile.calculate_scores()

        # Add to ML training data
        self.ml_predictor.add_training_sample(access_record, profile)

        # Update access probability prediction
        if self.ml_predictor.is_trained:
            profile.access_probability_score = (
                self.ml_predictor.predict_access_probability(access_record, profile)
            )

        # Report metrics
        if self.metrics_service:
            self.metrics_service.record_cache_operation(
                operation="access",
                cache_type="smart",
                hit=access_record.hit,
                duration=access_record.processing_time_ms / 1000.0,
            )

    # ========================================================================
    # ML-driven Optimizations
    # ========================================================================

    async def _predict_optimal_ttl(self, key: str, profile: CacheKeyProfile) -> int:
        """Predict optimal TTL for a key using ML and access patterns."""
        base_ttl = 3600  # 1 hour default

        # Adjust based on access pattern
        if profile.access_pattern == AccessPattern.HOTSPOT:
            # Hot data - longer TTL
            multiplier = 2.0 + profile.frequency_score
        elif profile.access_pattern == AccessPattern.TEMPORAL:
            # Temporal data - adaptive TTL
            if profile.inter_arrival_times:
                avg_interval = np.mean(profile.inter_arrival_times)
                multiplier = min(3.0, avg_interval / 1800)  # Max 3x for 30min intervals
            else:
                multiplier = 1.0
        elif profile.access_pattern == AccessPattern.SEASONAL:
            # Seasonal data - longer TTL with seasonality consideration
            multiplier = 1.5 + profile.seasonality_score
        else:
            # Random/sequential - standard TTL
            multiplier = 1.0

        # Adjust for frequency and recency
        multiplier *= 1.0 + profile.frequency_score * 0.5
        multiplier *= 1.0 + profile.recency_score * 0.3

        # ML prediction adjustment
        if self.ml_predictor.is_trained and profile.access_probability_score > 0:
            multiplier *= 1.0 + profile.access_probability_score

        optimal_ttl = int(base_ttl * multiplier)
        return min(optimal_ttl, 86400)  # Max 24 hours

    async def _intelligent_eviction(self) -> None:
        """Perform intelligent cache eviction using ML predictions."""
        if not self.key_profiles:
            return

        # Calculate eviction scores for all keys
        eviction_candidates = []

        for key, profile in self.key_profiles.items():
            # Check if key exists in cache
            if not self.redis_cache.exists(key):
                continue

            # Calculate eviction score (lower = more likely to evict)
            score = self._calculate_eviction_score(profile)
            eviction_candidates.append((key, score, profile))

        if not eviction_candidates:
            return

        # Sort by eviction score (ascending - lowest first)
        eviction_candidates.sort(key=lambda x: x[1])

        # Evict bottom 10% or at least 1 key
        num_to_evict = max(1, len(eviction_candidates) // 10)

        evicted_keys = []
        for key, _score, _profile in eviction_candidates[:num_to_evict]:
            if self.redis_cache.delete(key) > 0:
                evicted_keys.append(key)
                self.key_profiles.pop(key, None)

        self.performance_stats["eviction_decisions"] += len(evicted_keys)

        logger.info(f"Intelligent eviction: removed {len(evicted_keys)} keys")

    def _calculate_eviction_score(self, profile: CacheKeyProfile) -> float:
        """Calculate eviction score for a key (lower = more likely to evict)."""
        base_score = 1.0

        # Recency factor (recent access = higher score = less likely to evict)
        base_score += profile.recency_score * 2.0

        # Frequency factor
        base_score += min(profile.frequency_score, 2.0)  # Cap frequency impact

        # Access pattern factor
        pattern_bonus = {
            AccessPattern.HOTSPOT: 1.5,
            AccessPattern.TEMPORAL: 1.0,
            AccessPattern.SEASONAL: 1.2,
            AccessPattern.SEQUENTIAL: 0.8,
            AccessPattern.RANDOM: 0.5,
        }
        base_score += pattern_bonus.get(profile.access_pattern, 1.0)

        # ML prediction factor
        if profile.access_probability_score > 0:
            base_score += profile.access_probability_score * 1.5

        # Size penalty (larger items more likely to evict)
        if profile.avg_response_size > 10240:  # > 10KB
            base_score *= 0.8

        return base_score

    async def _intelligent_prefetch(
        self, accessed_key: str, access_record: AccessRecord
    ) -> None:
        """Perform intelligent prefetching based on access patterns."""
        if not self.ml_predictor.is_trained:
            return

        profile = self.key_profiles.get(accessed_key)
        if not profile:
            return

        # Get key cluster for pattern-based prefetching
        cluster_id = self.ml_predictor.get_key_cluster(access_record, profile)

        # Find related keys in the same cluster
        related_keys = []
        for key, key_profile in self.key_profiles.items():
            if key == accessed_key:
                continue

            # Create dummy access record for cluster prediction
            dummy_access = AccessRecord(key=key, timestamp=datetime.utcnow(), hit=False)

            key_cluster = self.ml_predictor.get_key_cluster(dummy_access, key_profile)

            if key_cluster == cluster_id and key_profile.access_probability_score > 0.7:
                related_keys.append(key)

        # Limit prefetch to top 3 related keys
        if related_keys:
            prefetch_keys = sorted(
                related_keys,
                key=lambda k: self.key_profiles[k].access_probability_score,
                reverse=True,
            )[:3]

            # Check which keys are not in cache and could benefit from prefetching
            for key in prefetch_keys:
                if not self.redis_cache.exists(key):
                    # This would trigger application-level prefetching
                    logger.debug(
                        f"Prefetch candidate: {key} (probability: {self.key_profiles[key].access_probability_score:.2f})"
                    )
                    self.performance_stats["prefetch_actions"] += 1

    async def _should_evict_for_space(self) -> bool:
        """Check if cache eviction is needed based on memory usage."""
        try:
            stats = self.redis_cache.get_stats()
            redis_info = stats.get("redis", {})

            # Check memory usage (if available)
            if "used_memory" in redis_info:
                # This is a simplified check - in production would use more sophisticated metrics
                return False  # Let Redis handle its own memory management for now

            return False
        except Exception:
            return False

    # ========================================================================
    # Background Optimization
    # ========================================================================

    async def start_optimization(self, interval_minutes: int = 30) -> None:
        """Start background optimization tasks."""
        if self.is_optimizing:
            return

        self.is_optimizing = True
        self.optimization_task = asyncio.create_task(
            self._optimization_loop(interval_minutes)
        )

        logger.info(
            f"Started smart cache optimization (interval: {interval_minutes}min)"
        )

    async def stop_optimization(self) -> None:
        """Stop background optimization."""
        if not self.is_optimizing:
            return

        self.is_optimizing = False

        if self.optimization_task:
            self.optimization_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.optimization_task

        logger.info("Stopped smart cache optimization")

    async def _run_optimization_cycle(self) -> None:
        if self.ml_predictor.needs_retraining():
            await self.ml_predictor.train_models()

        await self._cleanup_old_profiles()
        await self._analyze_access_patterns()
        await self._update_performance_metrics()

    async def _optimization_loop(self, interval_minutes: int) -> None:
        """Main optimization loop."""
        while self.is_optimizing:
            try:
                await self._run_optimization_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(60)
                continue

            await asyncio.sleep(interval_minutes * 60)

    async def _cleanup_old_profiles(self) -> None:
        """Clean up old and unused key profiles."""
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        old_keys = [
            key
            for key, profile in self.key_profiles.items()
            if profile.last_access < cutoff_time
        ]

        for key in old_keys:
            del self.key_profiles[key]

        if old_keys:
            logger.info(f"Cleaned up {len(old_keys)} old key profiles")

    async def _analyze_access_patterns(self) -> None:
        """Analyze overall access patterns for insights."""
        if not self.access_history:
            return

        # Analyze recent access patterns
        recent_accesses = [
            record
            for record in self.access_history
            if (datetime.utcnow() - record.timestamp).total_seconds() < 3600
        ]

        if not recent_accesses:
            return

        # Calculate hit rate
        hits = sum(1 for record in recent_accesses if record.hit)
        hit_rate = hits / len(recent_accesses) if recent_accesses else 0

        # Pattern distribution
        pattern_counts = defaultdict(int)
        for profile in self.key_profiles.values():
            pattern_counts[profile.access_pattern] += 1

        logger.info(
            f"Cache analysis - Hit rate: {hit_rate:.2f}, "
            f"Patterns: {dict(pattern_counts)}, "
            f"Active keys: {len(self.key_profiles)}"
        )

    async def _update_performance_metrics(self) -> None:
        """Update performance metrics for monitoring."""
        if not self.metrics_service:
            return

        try:
            # Calculate current hit rate
            total = self.performance_stats["total_requests"]
            if total > 0:
                hit_rate = (self.performance_stats["cache_hits"] / total) * 100
                self.metrics_service.record_cache_operation(
                    operation="performance_check", cache_type="smart", hit=hit_rate > 80
                )

            # Report ML prediction accuracy if available
            if self.performance_stats["ml_predictions_made"] > 0:
                # This would need actual accuracy tracking in a real implementation
                pass

        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")

    # ========================================================================
    # API and Reporting
    # ========================================================================

    def get_performance_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        # Calculate derived metrics
        total_requests = self.performance_stats["total_requests"]
        hit_rate = (
            (self.performance_stats["cache_hits"] / total_requests * 100)
            if total_requests > 0
            else 0
        )

        # Access pattern distribution
        pattern_distribution = defaultdict(int)
        for profile in self.key_profiles.values():
            pattern_distribution[profile.access_pattern.value] += 1

        # Top keys by various metrics
        top_frequent = sorted(
            self.key_profiles.values(), key=lambda p: p.frequency_score, reverse=True
        )[:10]

        top_recent = sorted(
            self.key_profiles.values(), key=lambda p: p.recency_score, reverse=True
        )[:10]

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "performance_stats": self.performance_stats.copy(),
            "cache_metrics": {
                "hit_rate_percent": round(hit_rate, 2),
                "total_keys": len(self.key_profiles),
                "ml_model_trained": self.ml_predictor.is_trained,
                "last_training": (
                    self.ml_predictor.last_training.isoformat()
                    if self.ml_predictor.last_training
                    else None
                ),
            },
            "access_patterns": dict(pattern_distribution),
            "top_keys": {
                "most_frequent": [
                    {
                        "key": p.key,
                        "frequency_score": round(p.frequency_score, 3),
                        "access_count": p.access_count,
                    }
                    for p in top_frequent
                ],
                "most_recent": [
                    {
                        "key": p.key,
                        "recency_score": round(p.recency_score, 3),
                        "last_access": p.last_access.isoformat(),
                    }
                    for p in top_recent
                ],
            },
        }

    def get_key_profile(self, key: str) -> dict[str, Any] | None:
        """Get detailed profile for a specific key."""
        profile = self.key_profiles.get(key)
        if not profile:
            return None

        return {
            "key": profile.key,
            "access_stats": {
                "total_accesses": profile.access_count,
                "hit_count": profile.hit_count,
                "miss_count": profile.miss_count,
                "hit_rate": (
                    (profile.hit_count / profile.access_count * 100)
                    if profile.access_count > 0
                    else 0
                ),
            },
            "timing": {
                "first_access": profile.first_access.isoformat(),
                "last_access": profile.last_access.isoformat(),
                "avg_processing_time_ms": round(profile.avg_processing_time, 2),
            },
            "pattern_analysis": {
                "access_pattern": profile.access_pattern.value,
                "frequency_score": round(profile.frequency_score, 3),
                "recency_score": round(profile.recency_score, 3),
                "seasonality_score": round(profile.seasonality_score, 3),
                "access_probability": round(profile.access_probability_score, 3),
            },
            "resource_usage": {
                "avg_response_size_bytes": int(profile.avg_response_size)
            },
            "predictions": {
                "predicted_next_access": (
                    profile.predicted_next_access.isoformat()
                    if profile.predicted_next_access
                    else None
                )
            },
        }


if __name__ == "__main__":
    # Example usage
    async def main() -> None:
        from .redis_cache_service import RedisCacheService, RedisConfig

        # Create Redis cache service
        redis_config = RedisConfig()
        redis_cache = RedisCacheService(redis_config)

        # Create smart cache manager
        smart_cache = SmartCacheManager(redis_cache)

        # Start optimization
        await smart_cache.start_optimization(interval_minutes=1)

        # Simulate some cache operations
        for i in range(20):
            key = f"test_key_{i % 5}"  # Create some repeated patterns

            # Set operation
            await smart_cache.set(key, f"value_{i}", user_id="user123")

            # Get operation
            await smart_cache.get(key, user_id="user123")

            await asyncio.sleep(0.1)  # Small delay

        # Wait a bit for analysis
        await asyncio.sleep(2)

        # Generate report
        report = smart_cache.get_performance_report()
        print(json.dumps(report, indent=2))

        await smart_cache.stop_optimization()

    # Run example
    # asyncio.run(main())
