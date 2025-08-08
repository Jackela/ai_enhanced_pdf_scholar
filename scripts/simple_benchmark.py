#!/usr/bin/env python3
"""
Simple Performance Benchmark Script
Establishes factual performance baselines for core AI Enhanced PDF Scholar operations.
"""

import json
import logging
import statistics
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import DatabaseConnection
from src.database import DatabaseMigrator


class SimpleBenchmark:
    """Simple benchmark suite for core operations"""
    
    def __init__(self):
        self.db_path = tempfile.mktemp(suffix='.db')
        self.db = None
        self.results = {}
    
    def setup_database(self):
        """Setup test database"""
        logger.info("Setting up test database...")
        self.db = DatabaseConnection(self.db_path)
        migrator = DatabaseMigrator(self.db)
        
        if migrator.needs_migration():
            migrator.migrate()
            
        logger.info("Database setup complete")
    
    def benchmark_basic_queries(self, runs: int = 50):
        """Benchmark basic database operations"""
        logger.info(f"Benchmarking basic database queries with {runs} runs")
        
        metrics = []
        
        # Test simple queries
        query_tests = [
            ("count_documents", "SELECT COUNT(*) FROM documents"),
            ("count_citations", "SELECT COUNT(*) FROM citations"),
            ("count_vector_indexes", "SELECT COUNT(*) FROM vector_indexes"),
            ("get_all_documents", "SELECT * FROM documents LIMIT 10"),
            ("get_recent_documents", "SELECT * FROM documents ORDER BY created_at DESC LIMIT 5")
        ]
        
        for query_name, query_sql in query_tests:
            query_times = []
            
            for run in range(runs):
                start_time = time.perf_counter()
                try:
                    result = self.db.fetch_all(query_sql)
                    result_count = len(result) if result else 0
                except Exception as e:
                    logger.warning(f"Query {query_name} failed: {e}")
                    continue
                    
                end_time = time.perf_counter()
                duration_ms = (end_time - start_time) * 1000
                query_times.append(duration_ms)
            
            if query_times:
                metrics.append({
                    "operation": query_name,
                    "run_count": len(query_times),
                    "min_ms": min(query_times),
                    "max_ms": max(query_times),
                    "avg_ms": statistics.mean(query_times),
                    "median_ms": statistics.median(query_times),
                    "p95_ms": statistics.quantiles(query_times, n=20)[18] if len(query_times) >= 20 else max(query_times)
                })
        
        self.results["database_queries"] = metrics
        return metrics
    
    def benchmark_file_operations(self, runs: int = 30):
        """Benchmark file I/O operations"""
        logger.info(f"Benchmarking file operations with {runs} runs")
        
        # Create temporary test files of different sizes
        test_dir = Path(tempfile.mkdtemp())
        test_files = {}
        
        # Small file (1KB)
        small_file = test_dir / "small.txt"
        small_file.write_text("x" * 1024)
        test_files["small_1kb"] = small_file
        
        # Medium file (100KB)
        medium_file = test_dir / "medium.txt"
        medium_file.write_text("x" * 102400)
        test_files["medium_100kb"] = medium_file
        
        # Large file (1MB)
        large_file = test_dir / "large.txt"
        large_file.write_text("x" * 1048576)
        test_files["large_1mb"] = large_file
        
        metrics = []
        
        for file_type, file_path in test_files.items():
            read_times = []
            
            for run in range(runs):
                start_time = time.perf_counter()
                try:
                    content = file_path.read_text()
                    content_length = len(content)
                except Exception as e:
                    logger.warning(f"File read {file_type} failed: {e}")
                    continue
                    
                end_time = time.perf_counter()
                duration_ms = (end_time - start_time) * 1000
                read_times.append(duration_ms)
            
            if read_times:
                metrics.append({
                    "operation": f"file_read_{file_type}",
                    "run_count": len(read_times),
                    "min_ms": min(read_times),
                    "max_ms": max(read_times),
                    "avg_ms": statistics.mean(read_times),
                    "median_ms": statistics.median(read_times),
                    "p95_ms": statistics.quantiles(read_times, n=20)[18] if len(read_times) >= 20 else max(read_times),
                    "file_size_bytes": file_path.stat().st_size,
                    "throughput_mb_per_sec": (file_path.stat().st_size / 1024 / 1024) / (statistics.mean(read_times) / 1000)
                })
        
        # Cleanup test files
        for file_path in test_files.values():
            file_path.unlink()
        test_dir.rmdir()
        
        self.results["file_operations"] = metrics
        return metrics
    
    def benchmark_text_processing(self, runs: int = 50):
        """Benchmark text processing operations"""
        logger.info(f"Benchmarking text processing with {runs} runs")
        
        # Test data of different sizes
        test_texts = {
            "short_text": "This is a short test document with some basic content. " * 5,
            "medium_text": "This is a medium-length test document with more content to process. " * 100,
            "long_text": "This is a long test document with substantial content for processing tests. " * 1000
        }
        
        metrics = []
        
        for text_type, text_content in test_texts.items():
            processing_times = []
            
            for run in range(runs):
                start_time = time.perf_counter()
                
                # Simulate text processing operations
                words = text_content.split()
                word_count = len(words)
                char_count = len(text_content)
                sentences = text_content.split('. ')
                sentence_count = len(sentences)
                
                # Basic text cleaning
                cleaned_text = text_content.strip().lower()
                
                end_time = time.perf_counter()
                duration_ms = (end_time - start_time) * 1000
                processing_times.append(duration_ms)
            
            if processing_times:
                metrics.append({
                    "operation": f"text_processing_{text_type}",
                    "run_count": len(processing_times),
                    "min_ms": min(processing_times),
                    "max_ms": max(processing_times),
                    "avg_ms": statistics.mean(processing_times),
                    "median_ms": statistics.median(processing_times),
                    "p95_ms": statistics.quantiles(processing_times, n=20)[18] if len(processing_times) >= 20 else max(processing_times),
                    "text_length_chars": len(text_content),
                    "word_count": len(text_content.split()),
                    "throughput_chars_per_sec": len(text_content) / (statistics.mean(processing_times) / 1000)
                })
        
        self.results["text_processing"] = metrics
        return metrics
    
    def run_all_benchmarks(self):
        """Run all benchmark tests"""
        logger.info("Starting simple benchmark suite...")
        start_time = time.time()
        
        try:
            self.setup_database()
            self.benchmark_basic_queries()
            self.benchmark_file_operations()
            self.benchmark_text_processing()
            
            end_time = time.time()
            
            # Add metadata
            self.results["metadata"] = {
                "benchmark_timestamp": datetime.now().isoformat(),
                "total_duration_seconds": end_time - start_time,
                "benchmark_version": "1.0.0",
                "environment": {
                    "python_version": sys.version,
                    "platform": sys.platform
                }
            }
            
            logger.info(f"Benchmark suite completed in {end_time - start_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Benchmark suite failed: {e}")
            self.results["error"] = str(e)
            raise
        finally:
            self.cleanup()
        
        return self.results
    
    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "="*80)
        print("SIMPLE PERFORMANCE BENCHMARK SUMMARY")
        print("="*80)
        
        if "error" in self.results:
            print(f"❌ BENCHMARK FAILED: {self.results['error']}")
            return
        
        # Overall timing
        if "metadata" in self.results:
            metadata = self.results["metadata"]
            print(f"⏱️  Total Runtime: {metadata['total_duration_seconds']:.2f} seconds")
            print(f"📅 Timestamp: {metadata['benchmark_timestamp']}")
        
        # Database queries
        if "database_queries" in self.results:
            print(f"\n📊 DATABASE QUERY PERFORMANCE:")
            for metric in self.results["database_queries"]:
                print(f"   {metric['operation']}:")
                print(f"     • Average: {metric['avg_ms']:.2f}ms")
                print(f"     • Median: {metric['median_ms']:.2f}ms")
                print(f"     • P95: {metric['p95_ms']:.2f}ms")
                print(f"     • Range: {metric['min_ms']:.2f}-{metric['max_ms']:.2f}ms")
        
        # File operations
        if "file_operations" in self.results:
            print(f"\n📁 FILE I/O PERFORMANCE:")
            for metric in self.results["file_operations"]:
                print(f"   {metric['operation']}:")
                print(f"     • Average: {metric['avg_ms']:.2f}ms")
                print(f"     • Size: {metric['file_size_bytes']:,} bytes")
                print(f"     • Throughput: {metric['throughput_mb_per_sec']:.2f} MB/s")
        
        # Text processing
        if "text_processing" in self.results:
            print(f"\n📝 TEXT PROCESSING PERFORMANCE:")
            for metric in self.results["text_processing"]:
                print(f"   {metric['operation']}:")
                print(f"     • Average: {metric['avg_ms']:.2f}ms")
                print(f"     • Text Length: {metric['text_length_chars']:,} chars")
                print(f"     • Throughput: {metric['throughput_chars_per_sec']:,.0f} chars/s")
        
        # Performance assessment
        print(f"\n🎯 PERFORMANCE ASSESSMENT:")
        all_avg_times = []
        
        for category in ["database_queries", "file_operations", "text_processing"]:
            if category in self.results:
                category_times = [m['avg_ms'] for m in self.results[category]]
                all_avg_times.extend(category_times)
        
        if all_avg_times:
            overall_avg = statistics.mean(all_avg_times)
            if overall_avg < 10:
                print("   ✅ EXCELLENT - Operations complete in <10ms on average")
            elif overall_avg < 50:
                print("   ✅ GOOD - Operations complete in <50ms on average")
            elif overall_avg < 200:
                print("   ⚠️  ACCEPTABLE - Operations complete in <200ms on average")
            else:
                print("   ❌ NEEDS OPTIMIZATION - Operations taking >200ms on average")
            
            print(f"   📈 Overall Average: {overall_avg:.2f}ms")
        
        print("\n" + "="*80)
    
    def save_results(self, filename: str = None):
        """Save results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"simple_benchmark_results_{timestamp}.json"
        
        output_path = Path(filename)
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        logger.info(f"Results saved to: {output_path}")
        return output_path
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.db:
                self.db.close_all_connections()
            if Path(self.db_path).exists():
                Path(self.db_path).unlink()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Performance Benchmark")
    parser.add_argument("--save", help="Save results to JSON file", action="store_true")
    parser.add_argument("--output", help="Output filename for results")
    
    args = parser.parse_args()
    
    try:
        benchmark = SimpleBenchmark()
        results = benchmark.run_all_benchmarks()
        benchmark.print_summary()
        
        if args.save:
            output_file = benchmark.save_results(args.output)
            print(f"\n💾 Results saved to: {output_file}")
        
        # Return appropriate exit code
        if "error" not in results:
            return 0
        else:
            return 1
    
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())