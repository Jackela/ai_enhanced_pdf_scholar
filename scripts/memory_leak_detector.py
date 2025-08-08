#!/usr/bin/env python3
"""
Memory Leak Detection Script

Extended runtime memory monitoring for detecting memory usage patterns and potential leaks.
Analyzes memory stability over sustained operations and generates health assessments.

Agent C3: Performance Baseline Testing Expert
Mission: Detect memory leaks and assess long-term memory stability
"""

import argparse
import json
import psutil
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import sys
import statistics
import gc

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import DatabaseConnection
from src.repositories.document_repository import DocumentRepository
from src.services.content_hash_service import ContentHashService


class MemoryLeakDetector:
    """Advanced memory leak detection and analysis system."""
    
    def __init__(self, duration_minutes: int = 10, sample_interval_seconds: int = 30):
        self.duration_minutes = duration_minutes
        self.sample_interval = sample_interval_seconds
        self.project_root = Path(__file__).parent.parent
        
        # Memory tracking data
        self.memory_samples: List[Dict[str, Any]] = []
        self.operation_logs: List[Dict[str, Any]] = []
        
        # Detection thresholds
        self.thresholds = {
            'leak_growth_mb_per_hour': 5.0,  # Growth >5MB/hour indicates leak
            'peak_to_baseline_ratio': 2.0,    # Peak >2x baseline indicates issues
            'gc_effectiveness_threshold': 0.8,  # GC should reclaim >80% of allocations
            'memory_stability_threshold': 0.9   # Memory should be stable >90% of time
        }
        
        # Database connection for testing
        self.db = None
        
    def run_memory_analysis(self) -> Dict[str, Any]:
        """Run comprehensive memory leak analysis."""
        print(f"🔍 Memory Leak Detection Analysis ({self.duration_minutes} minutes)")
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Sample interval: {self.sample_interval}s")
        
        # Initialize database connection if possible
        self._initialize_database()
        
        # Start memory monitoring
        monitoring_thread = self._start_memory_monitoring()
        
        # Run sustained operations for testing
        self._run_sustained_operations()
        
        # Wait for monitoring to complete
        monitoring_thread.join()
        
        # Analyze results
        analysis_results = self._analyze_memory_patterns()
        
        # Generate report
        self._generate_memory_report(analysis_results)
        
        # Save results
        self._save_analysis_results(analysis_results)
        
        return analysis_results
    
    def _initialize_database(self) -> None:
        """Initialize database connection for testing."""
        try:
            db_path = self.project_root / "data" / "memory_test.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.db = DatabaseConnection(str(db_path))
            print("✅ Database connection established for memory testing")
        except Exception as e:
            print(f"⚠️  Database connection failed: {e}")
            self.db = None
    
    def _start_memory_monitoring(self) -> threading.Thread:
        """Start background memory monitoring thread."""
        def monitor_memory():
            """Background memory monitoring function."""
            start_time = time.time()
            duration_seconds = self.duration_minutes * 60
            
            print(f"📊 Memory monitoring started for {self.duration_minutes} minutes...")
            
            while time.time() - start_time < duration_seconds:
                # Collect memory sample
                sample = self._collect_memory_sample()
                self.memory_samples.append(sample)
                
                # Print progress
                elapsed_minutes = (time.time() - start_time) / 60
                if len(self.memory_samples) % 10 == 0:  # Print every 10 samples
                    print(f"   📊 {elapsed_minutes:.1f}m: {sample['process_memory_mb']:.1f}MB RSS, "
                          f"{sample['system_memory_percent']:.1f}% system")
                
                # Wait for next sample
                time.sleep(self.sample_interval)
            
            print("📊 Memory monitoring completed")
        
        # Start monitoring thread
        thread = threading.Thread(target=monitor_memory, daemon=True)
        thread.start()
        return thread
    
    def _collect_memory_sample(self) -> Dict[str, Any]:
        """Collect comprehensive memory usage sample."""
        process = psutil.Process()
        system_memory = psutil.virtual_memory()
        
        # Force garbage collection and measure impact
        gc_before = len(gc.get_objects())
        memory_before_gc = process.memory_info().rss
        
        gc.collect()
        
        gc_after = len(gc.get_objects())
        memory_after_gc = process.memory_info().rss
        
        sample = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'elapsed_seconds': time.time() - (time.time() - len(self.memory_samples) * self.sample_interval),
            
            # Process memory metrics
            'process_memory_mb': process.memory_info().rss / 1024 / 1024,
            'process_memory_vms_mb': process.memory_info().vms / 1024 / 1024,
            'memory_percent': process.memory_percent(),
            
            # System memory metrics
            'system_memory_total_gb': system_memory.total / 1024 / 1024 / 1024,
            'system_memory_available_gb': system_memory.available / 1024 / 1024 / 1024,
            'system_memory_percent': system_memory.percent,
            
            # Garbage collection metrics
            'gc_objects_before': gc_before,
            'gc_objects_after': gc_after,
            'gc_objects_reclaimed': gc_before - gc_after,
            'memory_freed_by_gc_mb': (memory_before_gc - memory_after_gc) / 1024 / 1024,
            
            # CPU metrics
            'cpu_percent': process.cpu_percent(),
            'num_threads': process.num_threads()
        }
        
        return sample
    
    def _run_sustained_operations(self) -> None:
        """Run sustained operations to test for memory leaks."""
        print("🔄 Running sustained operations...")
        
        start_time = time.time()
        operation_count = 0
        
        # Run operations for the full duration
        while time.time() - start_time < (self.duration_minutes * 60):
            try:
                # Database operations (if available)
                if self.db:
                    self._perform_database_operations(operation_count)
                
                # Text processing operations
                self._perform_text_processing_operations(operation_count)
                
                # Memory allocation and deallocation patterns
                self._perform_memory_operations(operation_count)
                
                # Log operation
                self.operation_logs.append({
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'operation_id': operation_count,
                    'operation_type': 'sustained_test'
                })
                
                operation_count += 1
                
                # Brief pause between operations
                time.sleep(0.1)
                
            except Exception as e:
                print(f"   ⚠️  Operation error: {e}")
                continue
        
        print(f"✅ Completed {operation_count} sustained operations")
    
    def _perform_database_operations(self, operation_id: int) -> None:
        """Perform database operations for memory testing."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create test data
                test_title = f"Memory Test Document {operation_id}"
                test_path = f"/tmp/memory_test_{operation_id}.pdf"
                test_hash = f"hash_{operation_id:06d}"
                
                # Insert operation
                cursor.execute("""
                    INSERT OR REPLACE INTO documents (title, file_path, file_hash, file_size, page_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (test_title, test_path, test_hash, 1000, 5))
                
                # Query operation
                cursor.execute("SELECT COUNT(*) FROM documents")
                count = cursor.fetchone()[0]
                
                # Cleanup older test data to prevent database growth
                if operation_id % 100 == 0:
                    cursor.execute("""
                        DELETE FROM documents 
                        WHERE title LIKE 'Memory Test Document %' 
                        AND id < (SELECT MAX(id) - 50 FROM documents WHERE title LIKE 'Memory Test Document %')
                    """)
                
                conn.commit()
                
        except Exception as e:
            # Silently handle database errors during stress testing
            pass
    
    def _perform_text_processing_operations(self, operation_id: int) -> None:
        """Perform text processing operations that might cause memory leaks."""
        # Create and manipulate strings
        base_text = f"This is memory test operation number {operation_id}. " * 100
        
        # String operations that might cause fragmentation
        text_variations = []
        for i in range(10):
            variation = base_text.replace("operation", f"test_{i}").upper().lower()
            text_variations.append(variation)
        
        # Process text (simulate text analysis)
        word_counts = {}
        for text in text_variations:
            words = text.split()
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Cleanup local variables (explicit cleanup)
        del text_variations
        del word_counts
    
    def _perform_memory_operations(self, operation_id: int) -> None:
        """Perform operations that test memory allocation patterns."""
        # Create temporary data structures
        test_data = []
        
        # Allocate memory in chunks
        for i in range(50):
            chunk = [operation_id + j for j in range(100)]  # 100 integers
            test_data.append(chunk)
        
        # Process the data
        total = sum(sum(chunk) for chunk in test_data)
        
        # Explicit cleanup
        del test_data
        
        # Force occasional garbage collection
        if operation_id % 20 == 0:
            gc.collect()
    
    def _analyze_memory_patterns(self) -> Dict[str, Any]:
        """Analyze memory usage patterns for leaks and anomalies."""
        if not self.memory_samples:
            return {'error': 'No memory samples collected'}
        
        # Extract memory values
        memory_values = [sample['process_memory_mb'] for sample in self.memory_samples]
        timestamps = [datetime.fromisoformat(sample['timestamp'].replace('Z', '+00:00')) for sample in self.memory_samples]
        
        # Basic statistics
        initial_memory = memory_values[0]
        final_memory = memory_values[-1]
        peak_memory = max(memory_values)
        min_memory = min(memory_values)
        avg_memory = statistics.mean(memory_values)
        
        # Memory growth analysis
        memory_growth = final_memory - initial_memory
        total_hours = len(self.memory_samples) * self.sample_interval / 3600
        growth_rate_mb_per_hour = memory_growth / total_hours if total_hours > 0 else 0
        
        # Trend analysis (linear regression)
        trend_analysis = self._calculate_memory_trend(memory_values)
        
        # Stability analysis
        stability_analysis = self._analyze_memory_stability(memory_values)
        
        # Garbage collection effectiveness
        gc_analysis = self._analyze_gc_effectiveness()
        
        # Memory health assessment
        health_assessment = self._assess_memory_health(
            growth_rate_mb_per_hour, peak_memory, initial_memory, stability_analysis, gc_analysis
        )
        
        analysis = {
            'duration_minutes': self.duration_minutes,
            'sample_count': len(self.memory_samples),
            'memory_statistics': {
                'initial_mb': initial_memory,
                'final_mb': final_memory,
                'peak_mb': peak_memory,
                'min_mb': min_memory,
                'avg_mb': avg_memory,
                'memory_growth_mb': memory_growth,
                'growth_rate_mb_per_hour': growth_rate_mb_per_hour
            },
            'trend_analysis': trend_analysis,
            'stability_analysis': stability_analysis,
            'gc_analysis': gc_analysis,
            'health_assessment': health_assessment,
            'operations_completed': len(self.operation_logs),
            'thresholds': self.thresholds
        }
        
        return analysis
    
    def _calculate_memory_trend(self, memory_values: List[float]) -> Dict[str, Any]:
        """Calculate memory usage trend using linear regression."""
        n = len(memory_values)
        if n < 2:
            return {'error': 'Insufficient data for trend analysis'}
        
        x_values = list(range(n))
        
        # Linear regression calculations
        sum_x = sum(x_values)
        sum_y = sum(memory_values)
        sum_xy = sum(x * y for x, y in zip(x_values, memory_values))
        sum_xx = sum(x * x for x in x_values)
        
        # Slope (trend)
        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            slope = 0
        else:
            slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        # Correlation coefficient
        mean_x = sum_x / n
        mean_y = sum_y / n
        
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, memory_values))
        sum_sq_x = sum((x - mean_x) ** 2 for x in x_values)
        sum_sq_y = sum((y - mean_y) ** 2 for y in memory_values)
        
        if sum_sq_x == 0 or sum_sq_y == 0:
            correlation = 0
        else:
            correlation = numerator / (sum_sq_x * sum_sq_y) ** 0.5
        
        return {
            'slope_mb_per_sample': slope,
            'correlation_coefficient': correlation,
            'trend_strength': abs(correlation),
            'trend_direction': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable'
        }
    
    def _analyze_memory_stability(self, memory_values: List[float]) -> Dict[str, Any]:
        """Analyze memory usage stability."""
        if len(memory_values) < 3:
            return {'error': 'Insufficient data for stability analysis'}
        
        # Calculate moving averages and deviations
        window_size = min(10, len(memory_values) // 3)
        moving_averages = []
        
        for i in range(len(memory_values) - window_size + 1):
            window = memory_values[i:i + window_size]
            moving_averages.append(statistics.mean(window))
        
        # Stability metrics
        overall_std = statistics.stdev(memory_values)
        overall_cv = overall_std / statistics.mean(memory_values)  # Coefficient of variation
        
        # Detect memory spikes
        mean_memory = statistics.mean(memory_values)
        threshold = mean_memory + 2 * overall_std
        spikes = [v for v in memory_values if v > threshold]
        
        return {
            'standard_deviation_mb': overall_std,
            'coefficient_of_variation': overall_cv,
            'stability_score': max(0, 1 - overall_cv),  # Higher is more stable
            'memory_spikes_count': len(spikes),
            'largest_spike_mb': max(spikes) if spikes else 0,
            'is_stable': overall_cv < 0.1  # CV < 10% considered stable
        }
    
    def _analyze_gc_effectiveness(self) -> Dict[str, Any]:
        """Analyze garbage collection effectiveness."""
        if not self.memory_samples:
            return {'error': 'No GC data available'}
        
        gc_data = []
        memory_freed_data = []
        
        for sample in self.memory_samples:
            if 'gc_objects_reclaimed' in sample:
                gc_data.append(sample['gc_objects_reclaimed'])
            if 'memory_freed_by_gc_mb' in sample:
                memory_freed_data.append(sample['memory_freed_by_gc_mb'])
        
        if not gc_data:
            return {'error': 'No GC metrics collected'}
        
        # GC effectiveness metrics
        total_objects_reclaimed = sum(gc_data)
        avg_objects_reclaimed = statistics.mean(gc_data)
        total_memory_freed = sum(memory_freed_data)
        avg_memory_freed = statistics.mean(memory_freed_data) if memory_freed_data else 0
        
        return {
            'total_objects_reclaimed': total_objects_reclaimed,
            'avg_objects_per_gc': avg_objects_reclaimed,
            'total_memory_freed_mb': total_memory_freed,
            'avg_memory_freed_mb': avg_memory_freed,
            'gc_samples': len(gc_data),
            'gc_effectiveness_score': min(1.0, avg_objects_reclaimed / 1000)  # Normalize to 0-1
        }
    
    def _assess_memory_health(
        self, growth_rate: float, peak_memory: float, initial_memory: float,
        stability_analysis: Dict[str, Any], gc_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess overall memory health and detect leaks."""
        
        # Leak detection criteria
        leak_indicators = []
        health_score = 100
        
        # Growth rate analysis
        if growth_rate > self.thresholds['leak_growth_mb_per_hour']:
            leak_indicators.append(f"High growth rate: {growth_rate:.1f} MB/hour")
            health_score -= 30
        
        # Peak memory analysis
        peak_to_baseline_ratio = peak_memory / initial_memory if initial_memory > 0 else 1
        if peak_to_baseline_ratio > self.thresholds['peak_to_baseline_ratio']:
            leak_indicators.append(f"High peak ratio: {peak_to_baseline_ratio:.1f}x baseline")
            health_score -= 20
        
        # Stability analysis
        if not stability_analysis.get('is_stable', True):
            leak_indicators.append(f"Memory instability detected")
            health_score -= 20
        
        # GC effectiveness
        gc_score = gc_analysis.get('gc_effectiveness_score', 1.0)
        if gc_score < self.thresholds['gc_effectiveness_threshold']:
            leak_indicators.append(f"Poor GC effectiveness: {gc_score:.2f}")
            health_score -= 15
        
        # Memory spike analysis
        spike_count = stability_analysis.get('memory_spikes_count', 0)
        if spike_count > len(self.memory_samples) * 0.1:  # More than 10% samples are spikes
            leak_indicators.append(f"Frequent memory spikes: {spike_count}")
            health_score -= 15
        
        # Overall assessment
        health_score = max(0, health_score)
        
        if health_score >= 85:
            status = "✅ Healthy"
            recommendation = "Memory usage is stable and healthy"
        elif health_score >= 70:
            status = "⚠️ Monitor"
            recommendation = "Some concerns detected, monitor closely"
        else:
            status = "❌ Leak Detected"
            recommendation = "Memory leak detected, investigation required"
        
        return {
            'status': status,
            'health_score': health_score,
            'leak_indicators': leak_indicators,
            'recommendation': recommendation,
            'growth_rate_mb_per_hour': growth_rate,
            'peak_to_baseline_ratio': peak_to_baseline_ratio,
            'memory_stability': stability_analysis.get('is_stable', False)
        }
    
    def _generate_memory_report(self, analysis: Dict[str, Any]) -> None:
        """Generate comprehensive memory analysis report."""
        print("\n" + "="*70)
        print("🔍 MEMORY LEAK DETECTION ANALYSIS COMPLETE")
        print("="*70)
        
        # Duration and sample info
        print(f"📊 Analysis Duration: {analysis['duration_minutes']} minutes")
        print(f"📊 Samples Collected: {analysis['sample_count']}")
        print(f"🔄 Operations Completed: {analysis['operations_completed']}")
        
        # Memory statistics
        stats = analysis.get('memory_statistics', {})
        print(f"\n📈 Memory Pattern Analysis:")
        print(f"  - Initial Memory: {stats.get('initial_mb', 0):.1f} MB")
        print(f"  - Final Memory: {stats.get('final_mb', 0):.1f} MB")
        print(f"  - Peak Memory: {stats.get('peak_mb', 0):.1f} MB")
        print(f"  - Memory Growth Rate: {stats.get('growth_rate_mb_per_hour', 0):+.1f} MB/hour")
        
        # Trend analysis
        trend = analysis.get('trend_analysis', {})
        if 'error' not in trend:
            print(f"  - Trend Direction: {trend.get('trend_direction', 'unknown').title()}")
            print(f"  - Trend Strength: {trend.get('trend_strength', 0):.2f}")
        
        # Stability analysis
        stability = analysis.get('stability_analysis', {})
        if 'error' not in stability:
            print(f"  - Memory Stability: {'✅ Stable' if stability.get('is_stable', False) else '⚠️ Unstable'}")
            print(f"  - Memory Spikes: {stability.get('memory_spikes_count', 0)}")
        
        # Garbage collection effectiveness
        gc_analysis = analysis.get('gc_analysis', {})
        if 'error' not in gc_analysis:
            print(f"  - GC Effectiveness: {gc_analysis.get('gc_effectiveness_score', 0):.2f}")
            print(f"  - Memory Freed by GC: {gc_analysis.get('total_memory_freed_mb', 0):.1f} MB")
        
        # Health assessment
        health = analysis.get('health_assessment', {})
        print(f"\n🎯 Memory Health Assessment:")
        print(f"  - Status: {health.get('status', 'Unknown')}")
        print(f"  - Health Score: {health.get('health_score', 0):.0f}/100")
        
        leak_indicators = health.get('leak_indicators', [])
        if leak_indicators:
            print(f"  - Issues Detected:")
            for indicator in leak_indicators:
                print(f"    • {indicator}")
        else:
            print(f"  - No memory leaks detected")
        
        print(f"  - Recommendation: {health.get('recommendation', 'No recommendation')}")
        
        print("="*70)
    
    def _save_analysis_results(self, analysis: Dict[str, Any]) -> None:
        """Save memory analysis results to file."""
        results_dir = self.project_root / "performance_results"
        results_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"memory_leak_analysis_{timestamp}.json"
        
        # Prepare data for saving (convert any datetime objects to strings)
        save_data = {
            'metadata': {
                'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
                'duration_minutes': self.duration_minutes,
                'sample_interval_seconds': self.sample_interval,
                'total_samples': len(self.memory_samples),
                'total_operations': len(self.operation_logs)
            },
            'analysis_results': analysis,
            'raw_samples': self.memory_samples[:100],  # Save first 100 samples to avoid huge files
            'thresholds': self.thresholds
        }
        
        results_file = results_dir / filename
        with open(results_file, 'w') as f:
            json.dump(save_data, f, indent=2, default=str)
        
        print(f"💾 Memory analysis saved to: {results_file}")


def main():
    """Main memory leak detection function."""
    parser = argparse.ArgumentParser(description="Memory Leak Detection Analysis")
    parser.add_argument("--duration", type=int, default=10, 
                       help="Analysis duration in minutes (default: 10)")
    parser.add_argument("--interval", type=int, default=30,
                       help="Sample interval in seconds (default: 30)")
    
    args = parser.parse_args()
    
    try:
        detector = MemoryLeakDetector(args.duration, args.interval)
        results = detector.run_memory_analysis()
        
        # Determine exit code based on health assessment
        health = results.get('health_assessment', {})
        health_score = health.get('health_score', 0)
        
        if health_score >= 85:
            print("✅ Memory analysis passed - No leaks detected")
            return 0
        elif health_score >= 70:
            print("⚠️  Memory analysis passed with warnings")
            return 0
        else:
            print("❌ Memory leak detected - Investigation required")
            return 1
            
    except Exception as e:
        print(f"❌ Memory leak detection failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())