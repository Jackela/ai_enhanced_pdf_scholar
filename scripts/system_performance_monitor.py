#!/usr/bin/env python3
"""
System Performance Monitor
Comprehensive performance analysis for AI Enhanced PDF Scholar
Includes memory monitoring, concurrent load testing, and reliability assessment
"""

import asyncio
import concurrent.futures
import json
import logging
import os
import psutil
import sqlite3
import statistics
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import tempfile

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.database.connection import DatabaseConnection
    from src.services.enhanced_rag_service import EnhancedRAGService
except ImportError as e:
    logger.warning(f"Some dependencies not available: {e}")


@dataclass
class SystemMetrics:
    """System resource usage metrics"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    process_count: int
    timestamp: float


@dataclass
class DatabaseMetrics:
    """Database performance metrics"""
    query_count: int
    avg_query_time_ms: float
    min_query_time_ms: float
    max_query_time_ms: float
    total_time_ms: float
    errors: int
    concurrent_connections: int
    database_size_mb: float
    timestamp: float


@dataclass
class MemoryLeakTest:
    """Memory leak test results"""
    initial_memory_mb: float
    peak_memory_mb: float
    final_memory_mb: float
    memory_growth_mb: float
    operations_performed: int
    duration_seconds: float
    leak_detected: bool
    growth_rate_mb_per_operation: float


@dataclass
class ConcurrentLoadTest:
    """Concurrent load test results"""
    concurrent_users: int
    total_operations: int
    successful_operations: int
    failed_operations: int
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    operations_per_second: float
    error_rate_percent: float
    duration_seconds: float


@dataclass
class ReliabilityTest:
    """System reliability test results"""
    test_name: str
    iterations: int
    successful_iterations: int
    failed_iterations: int
    avg_recovery_time_ms: float
    max_recovery_time_ms: float
    reliability_score: float  # 0-1 scale
    error_messages: List[str]


class SystemPerformanceMonitor:
    """Comprehensive system performance monitoring and testing"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or "E:\\Code\\ai_enhanced_pdf_scholar\\data\\library.db"
        self.results = {}
        self.start_time = time.time()
        
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system resource metrics"""
        # CPU and Memory
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Disk I/O
        disk_io = psutil.disk_io_counters()
        disk_read_mb = disk_io.read_bytes / (1024 * 1024) if disk_io else 0
        disk_write_mb = disk_io.write_bytes / (1024 * 1024) if disk_io else 0
        
        # Network I/O
        network_io = psutil.net_io_counters()
        network_sent_mb = network_io.bytes_sent / (1024 * 1024) if network_io else 0
        network_recv_mb = network_io.bytes_recv / (1024 * 1024) if network_io else 0
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024 * 1024),
            memory_available_mb=memory.available / (1024 * 1024),
            disk_io_read_mb=disk_read_mb,
            disk_io_write_mb=disk_write_mb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            process_count=len(psutil.pids()),
            timestamp=time.time()
        )
    
    def monitor_system_resources(self, duration_seconds: int = 60, interval_seconds: int = 1) -> Dict[str, Any]:
        """Monitor system resources over time"""
        logger.info(f"Monitoring system resources for {duration_seconds} seconds...")
        
        metrics_history = []
        end_time = time.time() + duration_seconds
        
        while time.time() < end_time:
            metrics = self.get_system_metrics()
            metrics_history.append(asdict(metrics))
            time.sleep(interval_seconds)
        
        # Calculate statistics
        cpu_values = [m['cpu_percent'] for m in metrics_history]
        memory_values = [m['memory_percent'] for m in metrics_history]
        memory_used_values = [m['memory_used_mb'] for m in metrics_history]
        
        summary = {
            "monitoring_duration_seconds": duration_seconds,
            "total_measurements": len(metrics_history),
            "cpu_stats": {
                "avg_percent": statistics.mean(cpu_values),
                "min_percent": min(cpu_values),
                "max_percent": max(cpu_values),
                "std_dev": statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0
            },
            "memory_stats": {
                "avg_percent": statistics.mean(memory_values),
                "min_percent": min(memory_values),
                "max_percent": max(memory_values),
                "avg_used_mb": statistics.mean(memory_used_values),
                "peak_used_mb": max(memory_used_values)
            },
            "raw_metrics": metrics_history
        }
        
        logger.info(f"Resource monitoring complete. Average CPU: {summary['cpu_stats']['avg_percent']:.1f}%, Peak Memory: {summary['memory_stats']['peak_used_mb']:.0f}MB")
        
        return summary
    
    def test_database_performance(self, iterations: int = 100) -> DatabaseMetrics:
        """Test database performance with various queries"""
        logger.info(f"Testing database performance with {iterations} iterations...")
        
        query_times = []
        error_count = 0
        total_start = time.time()
        
        # Test queries that should work with existing schema
        test_queries = [
            "SELECT COUNT(*) FROM documents",
            "SELECT COUNT(*) FROM vector_indexes", 
            "SELECT id, title FROM documents LIMIT 10",
            "SELECT * FROM documents ORDER BY created_at DESC LIMIT 5",
            "SELECT d.id, d.title, v.chunk_count FROM documents d LEFT JOIN vector_indexes v ON d.id = v.document_id LIMIT 10"
        ]
        
        try:
            db_size = os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0
        except:
            db_size = 0
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            
            for i in range(iterations):
                query = test_queries[i % len(test_queries)]
                
                try:
                    start_time = time.time()
                    cursor = conn.execute(query)
                    results = cursor.fetchall()
                    end_time = time.time()
                    
                    query_time_ms = (end_time - start_time) * 1000
                    query_times.append(query_time_ms)
                    
                except Exception as e:
                    logger.warning(f"Query failed: {e}")
                    error_count += 1
        
        total_time = (time.time() - total_start) * 1000
        
        if query_times:
            metrics = DatabaseMetrics(
                query_count=len(query_times),
                avg_query_time_ms=statistics.mean(query_times),
                min_query_time_ms=min(query_times),
                max_query_time_ms=max(query_times),
                total_time_ms=total_time,
                errors=error_count,
                concurrent_connections=1,
                database_size_mb=db_size,
                timestamp=time.time()
            )
        else:
            metrics = DatabaseMetrics(
                query_count=0, avg_query_time_ms=0, min_query_time_ms=0,
                max_query_time_ms=0, total_time_ms=total_time, errors=error_count,
                concurrent_connections=1, database_size_mb=db_size, timestamp=time.time()
            )
        
        logger.info(f"Database performance test complete. Avg query time: {metrics.avg_query_time_ms:.2f}ms, Errors: {error_count}")
        
        return metrics
    
    def test_memory_leak(self, operations: int = 1000, operation_type: str = "database") -> MemoryLeakTest:
        """Test for memory leaks during repeated operations"""
        logger.info(f"Testing for memory leaks with {operations} {operation_type} operations...")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
        peak_memory = initial_memory
        
        start_time = time.time()
        
        # Perform repetitive operations
        for i in range(operations):
            try:
                if operation_type == "database":
                    with sqlite3.connect(self.db_path, timeout=5) as conn:
                        conn.execute("SELECT COUNT(*) FROM documents")
                        conn.fetchone()
                
                elif operation_type == "file_io":
                    # Create and delete temporary files
                    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                        f.write("test data " * 100)
                        temp_path = f.name
                    os.unlink(temp_path)
                
                elif operation_type == "text_processing":
                    # Simulate text processing operations
                    text = "Sample text for processing " * 1000
                    processed = text.upper().lower().split()
                    word_count = len(processed)
                
                # Monitor memory every 100 operations
                if i % 100 == 0:
                    current_memory = process.memory_info().rss / (1024 * 1024)
                    peak_memory = max(peak_memory, current_memory)
                    
            except Exception as e:
                logger.warning(f"Operation {i} failed: {e}")
        
        end_time = time.time()
        final_memory = process.memory_info().rss / (1024 * 1024)
        
        memory_growth = final_memory - initial_memory
        duration = end_time - start_time
        growth_rate = memory_growth / operations if operations > 0 else 0
        
        # Consider it a leak if memory grew by more than 10MB or 0.01MB per operation
        leak_detected = memory_growth > 10 or growth_rate > 0.01
        
        test_result = MemoryLeakTest(
            initial_memory_mb=initial_memory,
            peak_memory_mb=peak_memory,
            final_memory_mb=final_memory,
            memory_growth_mb=memory_growth,
            operations_performed=operations,
            duration_seconds=duration,
            leak_detected=leak_detected,
            growth_rate_mb_per_operation=growth_rate
        )
        
        logger.info(f"Memory leak test complete. Growth: {memory_growth:.2f}MB, Leak detected: {leak_detected}")
        
        return test_result
    
    def test_concurrent_load(self, concurrent_users: int = 10, operations_per_user: int = 50) -> ConcurrentLoadTest:
        """Test system performance under concurrent load"""
        logger.info(f"Testing concurrent load: {concurrent_users} users, {operations_per_user} operations each...")
        
        results = []
        errors = []
        start_time = time.time()
        
        def user_operations(user_id: int):
            """Simulate operations for a single user"""
            user_results = []
            user_errors = []
            
            for i in range(operations_per_user):
                op_start = time.time()
                
                try:
                    # Simulate various operations
                    with sqlite3.connect(self.db_path, timeout=10) as conn:
                        # Vary queries to simulate realistic usage
                        if i % 4 == 0:
                            conn.execute("SELECT COUNT(*) FROM documents").fetchone()
                        elif i % 4 == 1:
                            conn.execute("SELECT id, title FROM documents LIMIT 5").fetchall()
                        elif i % 4 == 2:
                            conn.execute("SELECT COUNT(*) FROM vector_indexes").fetchone()
                        else:
                            conn.execute("SELECT d.title, v.chunk_count FROM documents d LEFT JOIN vector_indexes v ON d.id = v.document_id LIMIT 3").fetchall()
                    
                    op_time = (time.time() - op_start) * 1000
                    user_results.append(op_time)
                    
                except Exception as e:
                    user_errors.append(str(e))
                    logger.debug(f"User {user_id} operation {i} failed: {e}")
            
            return user_results, user_errors
        
        # Execute concurrent operations
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(user_operations, user_id) for user_id in range(concurrent_users)]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    user_results, user_errors = future.result(timeout=30)
                    results.extend(user_results)
                    errors.extend(user_errors)
                except Exception as e:
                    logger.error(f"Concurrent test thread failed: {e}")
                    errors.append(str(e))
        
        total_time = time.time() - start_time
        
        if results:
            load_test = ConcurrentLoadTest(
                concurrent_users=concurrent_users,
                total_operations=concurrent_users * operations_per_user,
                successful_operations=len(results),
                failed_operations=len(errors),
                avg_response_time_ms=statistics.mean(results),
                min_response_time_ms=min(results),
                max_response_time_ms=max(results),
                operations_per_second=len(results) / total_time,
                error_rate_percent=(len(errors) / (concurrent_users * operations_per_user)) * 100,
                duration_seconds=total_time
            )
        else:
            load_test = ConcurrentLoadTest(
                concurrent_users=concurrent_users,
                total_operations=concurrent_users * operations_per_user,
                successful_operations=0,
                failed_operations=len(errors),
                avg_response_time_ms=0,
                min_response_time_ms=0,
                max_response_time_ms=0,
                operations_per_second=0,
                error_rate_percent=100,
                duration_seconds=total_time
            )
        
        logger.info(f"Concurrent load test complete. Success rate: {100 - load_test.error_rate_percent:.1f}%, Avg response: {load_test.avg_response_time_ms:.2f}ms")
        
        return load_test
    
    def test_system_reliability(self) -> List[ReliabilityTest]:
        """Test system reliability under various stress conditions"""
        logger.info("Testing system reliability...")
        
        reliability_tests = []
        
        # Test 1: Database connection resilience
        test_name = "database_connection_resilience"
        iterations = 50
        successful = 0
        failed = 0
        recovery_times = []
        errors = []
        
        for i in range(iterations):
            try:
                start_time = time.time()
                
                # Test rapid connection open/close cycles
                with sqlite3.connect(self.db_path, timeout=5) as conn:
                    conn.execute("SELECT 1").fetchone()
                
                recovery_time = (time.time() - start_time) * 1000
                recovery_times.append(recovery_time)
                successful += 1
                
            except Exception as e:
                failed += 1
                errors.append(str(e))
        
        reliability_tests.append(ReliabilityTest(
            test_name=test_name,
            iterations=iterations,
            successful_iterations=successful,
            failed_iterations=failed,
            avg_recovery_time_ms=statistics.mean(recovery_times) if recovery_times else 0,
            max_recovery_time_ms=max(recovery_times) if recovery_times else 0,
            reliability_score=successful / iterations,
            error_messages=list(set(errors))  # Unique errors only
        ))
        
        # Test 2: Resource exhaustion recovery
        test_name = "resource_exhaustion_recovery"
        iterations = 20
        successful = 0
        failed = 0
        recovery_times = []
        errors = []
        
        for i in range(iterations):
            try:
                start_time = time.time()
                
                # Create multiple simultaneous connections to test resource limits
                connections = []
                try:
                    for j in range(10):  # Create 10 connections
                        conn = sqlite3.connect(self.db_path, timeout=1)
                        connections.append(conn)
                        conn.execute("SELECT COUNT(*) FROM documents").fetchone()
                    
                    # Cleanup connections
                    for conn in connections:
                        conn.close()
                    
                    recovery_time = (time.time() - start_time) * 1000
                    recovery_times.append(recovery_time)
                    successful += 1
                    
                except Exception as conn_error:
                    # Cleanup any remaining connections
                    for conn in connections:
                        try:
                            conn.close()
                        except:
                            pass
                    raise conn_error
                    
            except Exception as e:
                failed += 1
                errors.append(str(e))
        
        reliability_tests.append(ReliabilityTest(
            test_name=test_name,
            iterations=iterations,
            successful_iterations=successful,
            failed_iterations=failed,
            avg_recovery_time_ms=statistics.mean(recovery_times) if recovery_times else 0,
            max_recovery_time_ms=max(recovery_times) if recovery_times else 0,
            reliability_score=successful / iterations,
            error_messages=list(set(errors))
        ))
        
        logger.info(f"System reliability tests complete. {len(reliability_tests)} tests performed.")
        
        return reliability_tests
    
    def run_comprehensive_assessment(self) -> Dict[str, Any]:
        """Run comprehensive performance and reliability assessment"""
        logger.info("Starting comprehensive system performance assessment...")
        
        assessment_start = time.time()
        
        try:
            # 1. System resource monitoring (30 seconds)
            logger.info("Phase 1: System resource monitoring...")
            resource_metrics = self.monitor_system_resources(duration_seconds=30, interval_seconds=2)
            
            # 2. Database performance testing
            logger.info("Phase 2: Database performance testing...")
            db_metrics = self.test_database_performance(iterations=200)
            
            # 3. Memory leak testing
            logger.info("Phase 3: Memory leak testing...")
            memory_leak_db = self.test_memory_leak(operations=500, operation_type="database")
            memory_leak_file = self.test_memory_leak(operations=300, operation_type="file_io")
            memory_leak_text = self.test_memory_leak(operations=1000, operation_type="text_processing")
            
            # 4. Concurrent load testing (multiple scenarios)
            logger.info("Phase 4: Concurrent load testing...")
            load_test_light = self.test_concurrent_load(concurrent_users=5, operations_per_user=20)
            load_test_moderate = self.test_concurrent_load(concurrent_users=10, operations_per_user=30)
            load_test_heavy = self.test_concurrent_load(concurrent_users=20, operations_per_user=25)
            
            # 5. System reliability testing
            logger.info("Phase 5: System reliability testing...")
            reliability_tests = self.test_system_reliability()
            
            assessment_duration = time.time() - assessment_start
            
            # Compile comprehensive results
            assessment_results = {
                "metadata": {
                    "assessment_start_time": assessment_start,
                    "assessment_duration_seconds": assessment_duration,
                    "timestamp": datetime.now().isoformat(),
                    "database_path": self.db_path,
                    "system_platform": sys.platform,
                    "python_version": sys.version
                },
                "system_resource_monitoring": resource_metrics,
                "database_performance": asdict(db_metrics),
                "memory_leak_tests": {
                    "database_operations": asdict(memory_leak_db),
                    "file_operations": asdict(memory_leak_file),
                    "text_processing": asdict(memory_leak_text)
                },
                "concurrent_load_tests": {
                    "light_load": asdict(load_test_light),
                    "moderate_load": asdict(load_test_moderate),
                    "heavy_load": asdict(load_test_heavy)
                },
                "reliability_tests": [asdict(test) for test in reliability_tests],
                "performance_summary": self.generate_performance_summary(
                    resource_metrics, db_metrics, [memory_leak_db, memory_leak_file, memory_leak_text],
                    [load_test_light, load_test_moderate, load_test_heavy], reliability_tests
                )
            }
            
            logger.info(f"Comprehensive assessment completed in {assessment_duration:.2f} seconds")
            
            return assessment_results
            
        except Exception as e:
            logger.error(f"Comprehensive assessment failed: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "assessment_duration_seconds": time.time() - assessment_start
            }
    
    def generate_performance_summary(self, resource_metrics: Dict, db_metrics: DatabaseMetrics, 
                                    memory_tests: List[MemoryLeakTest], load_tests: List[ConcurrentLoadTest],
                                    reliability_tests: List[ReliabilityTest]) -> Dict[str, Any]:
        """Generate performance summary and assessment"""
        
        # System performance score (0-100)
        cpu_score = max(0, 100 - resource_metrics['cpu_stats']['avg_percent'])
        memory_score = max(0, 100 - resource_metrics['memory_stats']['avg_percent'])
        system_score = (cpu_score + memory_score) / 2
        
        # Database performance score
        db_score = 100 if db_metrics.avg_query_time_ms < 1 else max(0, 100 - (db_metrics.avg_query_time_ms * 2))
        
        # Memory leak assessment
        memory_leaks_detected = sum(1 for test in memory_tests if test.leak_detected)
        memory_score = max(0, 100 - (memory_leaks_detected * 30))
        
        # Load test performance (based on error rate and response time)
        load_scores = []
        for load_test in load_tests:
            error_penalty = load_test.error_rate_percent * 2
            response_penalty = max(0, load_test.avg_response_time_ms - 10) * 0.5
            load_score = max(0, 100 - error_penalty - response_penalty)
            load_scores.append(load_score)
        
        avg_load_score = statistics.mean(load_scores) if load_scores else 0
        
        # Reliability score
        reliability_score = statistics.mean([test.reliability_score for test in reliability_tests]) * 100 if reliability_tests else 0
        
        # Overall performance score
        overall_score = statistics.mean([system_score, db_score, memory_score, avg_load_score, reliability_score])
        
        # Performance rating
        if overall_score >= 90:
            rating = "EXCELLENT"
        elif overall_score >= 75:
            rating = "GOOD"
        elif overall_score >= 60:
            rating = "ACCEPTABLE"
        elif overall_score >= 40:
            rating = "POOR"
        else:
            rating = "CRITICAL"
        
        # Production readiness assessment
        production_issues = []
        if db_metrics.avg_query_time_ms > 100:
            production_issues.append("Database queries too slow (>100ms)")
        if any(test.leak_detected for test in memory_tests):
            production_issues.append("Memory leaks detected")
        if any(test.error_rate_percent > 5 for test in load_tests):
            production_issues.append("High error rate under load (>5%)")
        if any(test.reliability_score < 0.95 for test in reliability_tests):
            production_issues.append("Reliability issues detected (<95% success rate)")
        if resource_metrics['memory_stats']['peak_used_mb'] > 2048:
            production_issues.append("High memory usage (>2GB)")
        
        production_ready = len(production_issues) == 0
        
        return {
            "overall_score": round(overall_score, 2),
            "performance_rating": rating,
            "component_scores": {
                "system_resources": round(system_score, 2),
                "database_performance": round(db_score, 2),
                "memory_management": round(memory_score, 2),
                "concurrent_load": round(avg_load_score, 2),
                "reliability": round(reliability_score, 2)
            },
            "production_readiness": {
                "ready": production_ready,
                "issues": production_issues,
                "recommendations": self.generate_recommendations(production_issues, overall_score)
            },
            "key_metrics": {
                "avg_query_time_ms": db_metrics.avg_query_time_ms,
                "peak_memory_mb": resource_metrics['memory_stats']['peak_used_mb'],
                "max_concurrent_users_supported": self.estimate_max_concurrent_users(load_tests),
                "system_reliability_percent": round(reliability_score, 1)
            }
        }
    
    def estimate_max_concurrent_users(self, load_tests: List[ConcurrentLoadTest]) -> int:
        """Estimate maximum concurrent users based on load test results"""
        # Find the highest successful user count with acceptable performance
        successful_tests = [test for test in load_tests if test.error_rate_percent < 5 and test.avg_response_time_ms < 100]
        
        if successful_tests:
            return max(test.concurrent_users for test in successful_tests)
        else:
            # Conservative estimate if all tests had issues
            return min(test.concurrent_users for test in load_tests) // 2
    
    def generate_recommendations(self, production_issues: List[str], overall_score: float) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        if overall_score < 60:
            recommendations.append("System requires immediate performance optimization before production deployment")
        
        if any("Database queries too slow" in issue for issue in production_issues):
            recommendations.append("Optimize database queries, add indexes for frequently accessed data")
            recommendations.append("Consider connection pooling for high-concurrency scenarios")
        
        if any("Memory leaks detected" in issue for issue in production_issues):
            recommendations.append("Investigate and fix memory leaks in application code")
            recommendations.append("Implement proper resource cleanup in all code paths")
        
        if any("High error rate under load" in issue for issue in production_issues):
            recommendations.append("Implement proper error handling and retry mechanisms")
            recommendations.append("Consider implementing circuit breaker patterns for external dependencies")
        
        if any("Reliability issues detected" in issue for issue in production_issues):
            recommendations.append("Improve error recovery and system resilience mechanisms")
        
        if any("High memory usage" in issue for issue in production_issues):
            recommendations.append("Optimize memory usage, consider implementing data streaming for large files")
            recommendations.append("Monitor memory usage in production and set up alerts")
        
        # General recommendations
        recommendations.extend([
            "Set up comprehensive monitoring and alerting for production deployment",
            "Implement health check endpoints for load balancer integration",
            "Consider implementing caching layers for frequently accessed data",
            "Establish performance baselines and regression testing in CI/CD pipeline"
        ])
        
        return recommendations
    
    def save_results(self, filename: str = None) -> str:
        """Save assessment results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"system_performance_assessment_{timestamp}.json"
        
        output_path = Path("performance_results") / filename
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        logger.info(f"Performance assessment results saved to: {output_path}")
        return str(output_path)


def main():
    """Main entry point for system performance monitoring"""
    import argparse
    
    parser = argparse.ArgumentParser(description="System Performance Monitor for AI Enhanced PDF Scholar")
    parser.add_argument("--db-path", help="Path to database file")
    parser.add_argument("--save", action="store_true", help="Save results to JSON file")
    parser.add_argument("--output-file", help="Output filename for results")
    
    args = parser.parse_args()
    
    try:
        monitor = SystemPerformanceMonitor(db_path=args.db_path)
        results = monitor.run_comprehensive_assessment()
        monitor.results = results
        
        # Print summary
        print("\n" + "="*100)
        print("SYSTEM PERFORMANCE ASSESSMENT SUMMARY")
        print("="*100)
        
        if "error" in results:
            print(f"❌ ASSESSMENT FAILED: {results['error']}")
        else:
            summary = results.get("performance_summary", {})
            print(f"📊 Overall Performance Score: {summary.get('overall_score', 0)}/100")
            print(f"🎯 Performance Rating: {summary.get('performance_rating', 'Unknown')}")
            
            # Component scores
            component_scores = summary.get("component_scores", {})
            print(f"\n📈 Component Scores:")
            for component, score in component_scores.items():
                print(f"   • {component.replace('_', ' ').title()}: {score}/100")
            
            # Key metrics
            key_metrics = summary.get("key_metrics", {})
            print(f"\n🔑 Key Metrics:")
            print(f"   • Average Query Time: {key_metrics.get('avg_query_time_ms', 0):.2f}ms")
            print(f"   • Peak Memory Usage: {key_metrics.get('peak_memory_mb', 0):.0f}MB")
            print(f"   • Max Concurrent Users: {key_metrics.get('max_concurrent_users_supported', 0)}")
            print(f"   • System Reliability: {key_metrics.get('system_reliability_percent', 0):.1f}%")
            
            # Production readiness
            readiness = summary.get("production_readiness", {})
            ready = readiness.get("ready", False)
            issues = readiness.get("issues", [])
            
            print(f"\n🚀 Production Readiness: {'✅ READY' if ready else '❌ NOT READY'}")
            if issues:
                print("   Issues to address:")
                for issue in issues:
                    print(f"   • {issue}")
        
        print("\n" + "="*100)
        
        # Save results if requested
        if args.save:
            output_file = monitor.save_results(args.output_file)
            print(f"\n💾 Results saved to: {output_file}")
        
        return 0 if "error" not in results else 1
        
    except Exception as e:
        logger.error(f"System performance assessment failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())