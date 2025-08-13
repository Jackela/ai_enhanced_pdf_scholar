"""
Performance Optimization Utilities for Parallel Test Execution

Provides intelligent test distribution, result caching, memory management,
and performance monitoring for enhanced parallel test execution.
"""

import hashlib
import json
import pickle
import psutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import sqlite3


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for test execution."""
    
    test_name: str
    execution_time_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    database_operations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    
    # Resource utilization
    peak_memory_mb: float = 0.0
    avg_cpu_percent: float = 0.0
    disk_io_mb: float = 0.0
    network_io_mb: float = 0.0
    
    # Execution context
    worker_id: str = ""
    isolation_strategy: str = ""
    parallel_factor: float = 1.0  # How much parallel execution helped
    
    # Quality metrics
    success: bool = True
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class CacheEntry:
    """Cache entry for test results and data."""
    
    key: str
    data: Any
    created_at: float
    accessed_at: float
    access_count: int = 0
    size_bytes: int = 0
    ttl_seconds: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl_seconds is None:
            return False
        return time.time() - self.created_at > self.ttl_seconds
    
    def touch(self):
        """Update access time and count."""
        self.accessed_at = time.time()
        self.access_count += 1


class IntelligentTestCache:
    """
    Intelligent caching system for test data, results, and fixtures.
    
    Features:
    - Multi-level caching (memory, disk, distributed)
    - Automatic cache invalidation
    - Size-based eviction
    - Performance-aware caching decisions
    """
    
    def __init__(
        self, 
        max_memory_mb: int = 512,
        max_disk_mb: int = 2048,
        default_ttl_seconds: float = 3600
    ):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.max_disk_bytes = max_disk_mb * 1024 * 1024
        self.default_ttl = default_ttl_seconds
        
        # Memory cache
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.memory_usage_bytes = 0
        
        # Disk cache setup
        self.cache_dir = Path(tempfile.gettempdir()) / "ai_pdf_test_cache"
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "disk_operations": 0,
            "total_requests": 0
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Performance monitoring
        self.performance_impact = {
            "cache_save_time_ms": [],
            "cache_load_time_ms": [],
            "eviction_time_ms": []
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache with intelligent promotion."""
        start_time = time.perf_counter()
        
        with self.lock:
            self.stats["total_requests"] += 1
            
            # Check memory cache first
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if not entry.is_expired():
                    entry.touch()
                    self.stats["hits"] += 1
                    return entry.data
                else:
                    # Remove expired entry
                    self._remove_from_memory(key)
            
            # Check disk cache
            disk_path = self._get_disk_path(key)
            if disk_path.exists():
                try:
                    with open(disk_path, 'rb') as f:
                        entry = pickle.load(f)
                    
                    if not entry.is_expired():
                        # Promote to memory cache if valuable
                        if self._should_promote_to_memory(entry):
                            self._add_to_memory(key, entry)
                        
                        entry.touch()
                        self.stats["hits"] += 1
                        self.stats["disk_operations"] += 1
                        return entry.data
                    else:
                        # Remove expired disk entry
                        disk_path.unlink(missing_ok=True)
                        
                except Exception as e:
                    print(f"Warning: Failed to load from disk cache: {e}")
            
            self.stats["misses"] += 1
            return None
    
    def set(
        self, 
        key: str, 
        data: Any, 
        ttl_seconds: Optional[float] = None,
        priority: str = "normal"  # "low", "normal", "high"
    ):
        """Set item in cache with intelligent placement."""
        start_time = time.perf_counter()
        
        with self.lock:
            ttl = ttl_seconds or self.default_ttl
            
            # Calculate data size
            try:
                serialized_data = pickle.dumps(data)
                size_bytes = len(serialized_data)
            except Exception:
                # Fallback size estimation
                size_bytes = len(str(data).encode('utf-8'))
                serialized_data = None
            
            entry = CacheEntry(
                key=key,
                data=data,
                created_at=time.time(),
                accessed_at=time.time(),
                size_bytes=size_bytes,
                ttl_seconds=ttl
            )
            
            # Decide cache placement based on size and priority
            if size_bytes < 1024 * 1024 and priority in ["normal", "high"]:  # < 1MB
                self._add_to_memory(key, entry)
            else:
                self._add_to_disk(key, entry, serialized_data)
            
            save_time = (time.perf_counter() - start_time) * 1000
            self.performance_impact["cache_save_time_ms"].append(save_time)
    
    def _add_to_memory(self, key: str, entry: CacheEntry):
        """Add entry to memory cache with eviction management."""
        # Check if we need to evict
        while (self.memory_usage_bytes + entry.size_bytes > self.max_memory_bytes and 
               self.memory_cache):
            self._evict_from_memory()
        
        # Add entry
        if key in self.memory_cache:
            self.memory_usage_bytes -= self.memory_cache[key].size_bytes
        
        self.memory_cache[key] = entry
        self.memory_usage_bytes += entry.size_bytes
    
    def _add_to_disk(self, key: str, entry: CacheEntry, serialized_data: Optional[bytes] = None):
        """Add entry to disk cache."""
        try:
            disk_path = self._get_disk_path(key)
            
            if serialized_data is None:
                serialized_data = pickle.dumps(entry)
            else:
                # Wrap data in CacheEntry
                entry_data = pickle.dumps(entry)
                serialized_data = entry_data
            
            with open(disk_path, 'wb') as f:
                f.write(serialized_data)
                
            self.stats["disk_operations"] += 1
            
        except Exception as e:
            print(f"Warning: Failed to save to disk cache: {e}")
    
    def _remove_from_memory(self, key: str):
        """Remove entry from memory cache."""
        if key in self.memory_cache:
            self.memory_usage_bytes -= self.memory_cache[key].size_bytes
            del self.memory_cache[key]
    
    def _evict_from_memory(self):
        """Evict least valuable entry from memory cache."""
        if not self.memory_cache:
            return
        
        # Find least recently used entry
        lru_key = min(
            self.memory_cache.keys(),
            key=lambda k: self.memory_cache[k].accessed_at
        )
        
        # Move to disk if valuable
        entry = self.memory_cache[lru_key]
        if entry.access_count > 1:  # Has been accessed multiple times
            self._add_to_disk(lru_key, entry)
        
        self._remove_from_memory(lru_key)
        self.stats["evictions"] += 1
    
    def _should_promote_to_memory(self, entry: CacheEntry) -> bool:
        """Determine if disk entry should be promoted to memory."""
        # Promote if:
        # 1. Small size (< 1MB)
        # 2. Frequently accessed
        # 3. Recently created
        
        is_small = entry.size_bytes < 1024 * 1024  # 1MB
        is_frequent = entry.access_count > 2
        is_recent = time.time() - entry.created_at < 300  # 5 minutes
        
        return is_small and (is_frequent or is_recent)
    
    def _get_disk_path(self, key: str) -> Path:
        """Get disk path for cache key."""
        # Hash key to avoid file system issues
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def clear(self):
        """Clear all caches."""
        with self.lock:
            # Clear memory
            self.memory_cache.clear()
            self.memory_usage_bytes = 0
            
            # Clear disk
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                except Exception:
                    pass
            
            # Reset stats
            self.stats = {k: 0 for k in self.stats}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.stats["total_requests"]
            hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0
            
            return {
                "memory_cache_size": len(self.memory_cache),
                "memory_usage_mb": self.memory_usage_bytes / (1024 * 1024),
                "disk_cache_files": len(list(self.cache_dir.glob("*.cache"))),
                "hit_rate": hit_rate,
                "total_requests": total_requests,
                **self.stats,
                "performance_impact": {
                    "avg_save_time_ms": sum(self.performance_impact["cache_save_time_ms"]) / 
                                       len(self.performance_impact["cache_save_time_ms"])
                                       if self.performance_impact["cache_save_time_ms"] else 0,
                    "avg_load_time_ms": sum(self.performance_impact["cache_load_time_ms"]) / 
                                       len(self.performance_impact["cache_load_time_ms"])
                                       if self.performance_impact["cache_load_time_ms"] else 0
                }
            }


class TestResourceMonitor:
    """
    Monitors system resources during test execution and provides
    intelligent resource management recommendations.
    """
    
    def __init__(self):
        self.monitoring_active = False
        self.metrics: List[Dict[str, Any]] = []
        self.baseline_metrics: Optional[Dict[str, Any]] = None
        self.resource_alerts: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        
        # Thresholds
        self.memory_warning_threshold = 85.0  # % of system memory
        self.memory_critical_threshold = 95.0
        self.cpu_warning_threshold = 80.0     # % CPU usage
        self.disk_io_warning_threshold = 100.0  # MB/s
        
    def start_monitoring(self, test_name: str) -> str:
        """Start monitoring resources for a test."""
        monitor_id = f"{test_name}_{int(time.time())}"
        
        with self.lock:
            if not self.monitoring_active:
                self.baseline_metrics = self._get_current_metrics()
                self.monitoring_active = True
            
            return monitor_id
    
    def stop_monitoring(self, monitor_id: str) -> PerformanceMetrics:
        """Stop monitoring and return metrics."""
        with self.lock:
            current_metrics = self._get_current_metrics()
            
            if self.baseline_metrics:
                # Calculate deltas
                memory_delta = (current_metrics["memory_percent"] - 
                              self.baseline_metrics["memory_percent"])
                cpu_delta = (current_metrics["cpu_percent"] - 
                            self.baseline_metrics["cpu_percent"])
                
                # Extract test name from monitor_id
                test_name = monitor_id.split("_")[0] if "_" in monitor_id else monitor_id
                
                metrics = PerformanceMetrics(
                    test_name=test_name,
                    execution_time_ms=0,  # Will be set by caller
                    memory_usage_mb=current_metrics["memory_used_mb"],
                    cpu_usage_percent=current_metrics["cpu_percent"],
                    peak_memory_mb=current_metrics["memory_used_mb"],
                    avg_cpu_percent=cpu_delta,
                    disk_io_mb=current_metrics.get("disk_io_mb", 0),
                    network_io_mb=current_metrics.get("network_io_mb", 0)
                )
                
                return metrics
            
            # Fallback metrics
            return PerformanceMetrics(
                test_name=monitor_id.split("_")[0] if "_" in monitor_id else monitor_id,
                execution_time_ms=0,
                memory_usage_mb=current_metrics["memory_used_mb"],
                cpu_usage_percent=current_metrics["cpu_percent"]
            )
    
    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Disk I/O metrics
            disk_io = psutil.disk_io_counters()
            disk_io_mb = 0
            if disk_io:
                # Convert bytes to MB
                disk_io_mb = (disk_io.read_bytes + disk_io.write_bytes) / (1024 * 1024)
            
            # Network I/O metrics
            network_io = psutil.net_io_counters()
            network_io_mb = 0
            if network_io:
                network_io_mb = (network_io.bytes_sent + network_io.bytes_recv) / (1024 * 1024)
            
            return {
                "timestamp": time.time(),
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_available_mb": memory.available / (1024 * 1024),
                "cpu_percent": cpu_percent,
                "disk_io_mb": disk_io_mb,
                "network_io_mb": network_io_mb
            }
            
        except Exception as e:
            print(f"Warning: Failed to get system metrics: {e}")
            return {
                "timestamp": time.time(),
                "memory_percent": 0,
                "memory_used_mb": 0,
                "memory_available_mb": 0,
                "cpu_percent": 0,
                "disk_io_mb": 0,
                "network_io_mb": 0
            }
    
    def check_resource_pressure(self) -> Dict[str, Any]:
        """Check for resource pressure and return recommendations."""
        current = self._get_current_metrics()
        
        alerts = []
        recommendations = []
        
        # Memory pressure check
        if current["memory_percent"] > self.memory_critical_threshold:
            alerts.append({
                "type": "memory_critical",
                "message": f"Critical memory usage: {current['memory_percent']:.1f}%",
                "severity": "critical"
            })
            recommendations.append("Reduce parallel workers and enable memory-constrained mode")
            
        elif current["memory_percent"] > self.memory_warning_threshold:
            alerts.append({
                "type": "memory_warning", 
                "message": f"High memory usage: {current['memory_percent']:.1f}%",
                "severity": "warning"
            })
            recommendations.append("Consider reducing test concurrency")
        
        # CPU pressure check
        if current["cpu_percent"] > self.cpu_warning_threshold:
            alerts.append({
                "type": "cpu_warning",
                "message": f"High CPU usage: {current['cpu_percent']:.1f}%",
                "severity": "warning"
            })
            recommendations.append("CPU-bound - parallel execution may not help")
        
        # Disk I/O check
        if current["disk_io_mb"] > self.disk_io_warning_threshold:
            alerts.append({
                "type": "disk_io_warning",
                "message": f"High disk I/O: {current['disk_io_mb']:.1f} MB/s",
                "severity": "warning"
            })
            recommendations.append("I/O bound - consider SSD or reduce database operations")
        
        return {
            "resource_pressure": len(alerts) > 0,
            "alerts": alerts,
            "recommendations": recommendations,
            "current_metrics": current
        }
    
    def get_resource_summary(self) -> Dict[str, Any]:
        """Get summary of resource usage during monitoring."""
        with self.lock:
            if not self.metrics:
                return {"error": "No metrics collected"}
            
            # Calculate summary statistics
            memory_values = [m["memory_percent"] for m in self.metrics]
            cpu_values = [m["cpu_percent"] for m in self.metrics]
            
            return {
                "total_samples": len(self.metrics),
                "memory": {
                    "avg_percent": sum(memory_values) / len(memory_values),
                    "max_percent": max(memory_values),
                    "min_percent": min(memory_values)
                },
                "cpu": {
                    "avg_percent": sum(cpu_values) / len(cpu_values),
                    "max_percent": max(cpu_values),
                    "min_percent": min(cpu_values)
                },
                "alerts_count": len(self.resource_alerts)
            }


class IntelligentTestDistribution:
    """
    Intelligently distributes tests across workers based on characteristics,
    resource requirements, and historical performance data.
    """
    
    def __init__(self, cache: IntelligentTestCache, monitor: TestResourceMonitor):
        self.cache = cache
        self.monitor = monitor
        self.historical_data: Dict[str, List[PerformanceMetrics]] = {}
        self.worker_capabilities: Dict[str, Dict[str, Any]] = {}
        
    def distribute_tests(
        self,
        tests: List[Tuple[str, Dict[str, Any]]],  # (test_name, characteristics)
        available_workers: int,
        resource_constraints: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Distribute tests optimally across workers.
        
        Returns mapping of worker_id -> list of test names
        """
        
        # Load historical performance data
        self._load_historical_data()
        
        # Analyze current resource state
        resource_state = self.monitor.check_resource_pressure()
        
        # Calculate optimal distribution
        distribution = self._calculate_optimal_distribution(
            tests, available_workers, resource_constraints, resource_state
        )
        
        return distribution
    
    def _load_historical_data(self):
        """Load historical performance data from cache."""
        historical_key = "test_performance_history"
        cached_data = self.cache.get(historical_key)
        
        if cached_data:
            self.historical_data = cached_data
        else:
            # Initialize empty historical data
            self.historical_data = {}
    
    def _calculate_optimal_distribution(
        self,
        tests: List[Tuple[str, Dict[str, Any]]],
        available_workers: int,
        resource_constraints: Dict[str, Any],
        resource_state: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Calculate optimal test distribution."""
        
        # Sort tests by estimated duration (longest first for better load balancing)
        tests_sorted = sorted(
            tests,
            key=lambda x: x[1].get("estimated_duration_ms", 100),
            reverse=True
        )
        
        # Initialize worker assignments
        worker_loads: Dict[str, Dict[str, Any]] = {}
        for i in range(available_workers):
            worker_id = f"worker_{i}"
            worker_loads[worker_id] = {
                "tests": [],
                "total_duration_ms": 0,
                "memory_requirement_mb": 0,
                "cpu_requirement": 0,
                "io_operations": 0
            }
        
        # Distribute tests using intelligent assignment
        for test_name, characteristics in tests_sorted:
            best_worker = self._find_best_worker(
                test_name, characteristics, worker_loads, resource_state
            )
            
            # Assign test to best worker
            worker_loads[best_worker]["tests"].append(test_name)
            worker_loads[best_worker]["total_duration_ms"] += characteristics.get("estimated_duration_ms", 100)
            worker_loads[best_worker]["memory_requirement_mb"] += characteristics.get("memory_requirement_mb", 10)
            worker_loads[best_worker]["cpu_requirement"] += characteristics.get("cpu_requirement", 1)
            worker_loads[best_worker]["io_operations"] += characteristics.get("database_operations", 0)
        
        # Extract final distribution
        distribution = {
            worker_id: data["tests"]
            for worker_id, data in worker_loads.items()
            if data["tests"]  # Only include workers with tests
        }
        
        return distribution
    
    def _find_best_worker(
        self,
        test_name: str,
        characteristics: Dict[str, Any],
        worker_loads: Dict[str, Dict[str, Any]],
        resource_state: Dict[str, Any]
    ) -> str:
        """Find the best worker for a specific test."""
        
        scores = {}
        
        for worker_id, load_data in worker_loads.items():
            score = 0.0
            
            # Load balancing score (prefer workers with less total duration)
            max_duration = max((data["total_duration_ms"] for data in worker_loads.values()), default=1)
            if max_duration > 0:
                load_factor = load_data["total_duration_ms"] / max_duration
                score += (1.0 - load_factor) * 40  # 40% weight for load balancing
            
            # Resource compatibility score
            memory_compat = self._calculate_memory_compatibility(
                characteristics.get("memory_requirement_mb", 10),
                load_data["memory_requirement_mb"],
                resource_state
            )
            score += memory_compat * 30  # 30% weight for memory compatibility
            
            # Historical performance score
            historical_score = self._get_historical_performance_score(
                test_name, worker_id
            )
            score += historical_score * 20  # 20% weight for historical performance
            
            # Affinity score (similar tests work well together)
            affinity_score = self._calculate_affinity_score(
                characteristics, load_data["tests"]
            )
            score += affinity_score * 10  # 10% weight for test affinity
            
            scores[worker_id] = score
        
        # Return worker with highest score
        return max(scores.keys(), key=lambda w: scores[w])
    
    def _calculate_memory_compatibility(
        self,
        test_memory_mb: float,
        worker_current_mb: float,
        resource_state: Dict[str, Any]
    ) -> float:
        """Calculate memory compatibility score (0-1)."""
        
        # Get system memory state
        system_memory_percent = resource_state.get("current_metrics", {}).get("memory_percent", 50)
        
        # Estimate total memory if this test is added
        estimated_total = worker_current_mb + test_memory_mb
        
        # Score based on memory pressure
        if system_memory_percent > 90:
            # High memory pressure - penalize memory-intensive tests
            if estimated_total > 100:  # > 100MB
                return 0.1
            elif estimated_total > 50:  # > 50MB
                return 0.5
            else:
                return 1.0
        elif system_memory_percent > 70:
            # Medium memory pressure
            if estimated_total > 200:  # > 200MB
                return 0.3
            elif estimated_total > 100:  # > 100MB
                return 0.7
            else:
                return 1.0
        else:
            # Low memory pressure - memory is not a constraint
            return 1.0
    
    def _get_historical_performance_score(self, test_name: str, worker_id: str) -> float:
        """Get historical performance score for test on specific worker."""
        
        if test_name not in self.historical_data:
            return 0.5  # Neutral score for new tests
        
        # Find historical runs on this worker
        worker_runs = [
            metrics for metrics in self.historical_data[test_name]
            if metrics.worker_id == worker_id
        ]
        
        if not worker_runs:
            return 0.5  # Neutral score for new worker
        
        # Calculate average performance score
        # Better performance = higher score
        total_score = 0.0
        for run in worker_runs:
            # Score based on success rate, execution time, and resource usage
            success_score = 1.0 if run.success else 0.0
            
            # Normalize execution time (faster = better)
            time_score = max(0.0, 1.0 - (run.execution_time_ms / 10000))  # Normalize to 10s
            
            # Normalize memory usage (less = better)
            memory_score = max(0.0, 1.0 - (run.memory_usage_mb / 100))  # Normalize to 100MB
            
            run_score = (success_score * 0.5 + time_score * 0.3 + memory_score * 0.2)
            total_score += run_score
        
        return total_score / len(worker_runs)
    
    def _calculate_affinity_score(
        self,
        test_characteristics: Dict[str, Any],
        worker_tests: List[str]
    ) -> float:
        """Calculate affinity score based on similar test characteristics."""
        
        if not worker_tests:
            return 0.5  # Neutral score for empty worker
        
        # For simplicity, return neutral score
        # In a full implementation, you would analyze characteristics
        # of tests already assigned to the worker
        return 0.5
    
    def record_performance(self, test_name: str, metrics: PerformanceMetrics):
        """Record performance metrics for future optimization."""
        
        if test_name not in self.historical_data:
            self.historical_data[test_name] = []
        
        self.historical_data[test_name].append(metrics)
        
        # Keep only recent history (last 10 runs)
        if len(self.historical_data[test_name]) > 10:
            self.historical_data[test_name] = self.historical_data[test_name][-10:]
        
        # Cache the updated historical data
        self.cache.set("test_performance_history", self.historical_data, ttl_seconds=86400)  # 24 hours
    
    def get_optimization_recommendations(self) -> List[str]:
        """Get recommendations for test execution optimization."""
        recommendations = []
        
        # Analyze resource state
        resource_state = self.monitor.check_resource_pressure()
        
        if resource_state["resource_pressure"]:
            recommendations.extend(resource_state["recommendations"])
        
        # Analyze historical performance
        if self.historical_data:
            slow_tests = []
            for test_name, metrics_list in self.historical_data.items():
                avg_duration = sum(m.execution_time_ms for m in metrics_list) / len(metrics_list)
                if avg_duration > 5000:  # > 5 seconds
                    slow_tests.append((test_name, avg_duration))
            
            if slow_tests:
                recommendations.append(
                    f"Consider optimizing {len(slow_tests)} slow tests: "
                    f"{', '.join(name for name, _ in slow_tests[:3])}"
                )
        
        # Cache performance analysis
        cache_stats = self.cache.get_stats()
        if cache_stats["hit_rate"] < 0.5:
            recommendations.append("Low cache hit rate - consider increasing cache size or TTL")
        
        return recommendations


# Global instances for performance optimization
_global_cache: Optional[IntelligentTestCache] = None
_global_monitor: Optional[TestResourceMonitor] = None
_global_distributor: Optional[IntelligentTestDistribution] = None

def get_performance_cache() -> IntelligentTestCache:
    """Get global performance cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = IntelligentTestCache()
    return _global_cache

def get_resource_monitor() -> TestResourceMonitor:
    """Get global resource monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = TestResourceMonitor()
    return _global_monitor

def get_test_distributor() -> IntelligentTestDistribution:
    """Get global test distributor instance."""
    global _global_distributor
    if _global_distributor is None:
        cache = get_performance_cache()
        monitor = get_resource_monitor()
        _global_distributor = IntelligentTestDistribution(cache, monitor)
    return _global_distributor