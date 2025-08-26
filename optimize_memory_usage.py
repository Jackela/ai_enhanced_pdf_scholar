#!/usr/bin/env python3
"""
Memory Usage Optimization Script

This script identifies and fixes memory leaks and optimizes memory usage patterns
in the AI Enhanced PDF Scholar application.
"""

import gc
import sys
import time
import tracemalloc
from pathlib import Path

import psutil

# Add project root to path
sys.path.append('.')

def analyze_memory_usage():
    """Analyze current memory usage patterns."""
    print("🔍 Memory Usage Analysis")
    print("=" * 50)

    # Start memory tracing
    tracemalloc.start()

    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    print(f"Initial Memory Usage: {initial_memory:.2f} MB")

    try:
        # Test database operations for memory leaks
        print("\n1. Testing database connection memory usage...")

        from src.database.connection import DatabaseConnection

        # Test multiple database operations
        db_path = Path.home() / ".ai_pdf_scholar" / "test_memory.db"
        db_path.parent.mkdir(exist_ok=True)

        memory_samples = []

        for i in range(10):
            # Create and use database connection
            db = DatabaseConnection(str(db_path))

            # Perform some operations
            with db.get_cursor() as cursor:
                cursor.execute("CREATE TABLE IF NOT EXISTS test_memory (id INTEGER PRIMARY KEY, data TEXT)")
                cursor.execute("INSERT INTO test_memory (data) VALUES (?)", (f"test_data_{i}",))

            # Force close connections
            db.close_all_connections()

            # Force garbage collection
            gc.collect()

            # Measure memory
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)

            print(f"   Operation {i+1}: {current_memory:.2f} MB")

            time.sleep(0.1)  # Small delay

        # Analyze memory growth
        memory_growth = memory_samples[-1] - memory_samples[0]
        avg_growth_per_op = memory_growth / len(memory_samples)

        print("\n   📊 Database Memory Analysis:")
        print(f"   - Total growth: {memory_growth:.3f} MB")
        print(f"   - Average per operation: {avg_growth_per_op:.3f} MB")

        if avg_growth_per_op > 0.01:  # 10KB per operation
            print("   ⚠️  Potential memory leak detected")
        else:
            print("   ✅ Memory usage stable")

        # Clean up test database
        db_path.unlink(missing_ok=True)

        # Test RAG service memory usage
        print("\n2. Testing RAG service memory usage...")

        try:
            from config import Config
            from src.services.enhanced_rag_service import EnhancedRAGService

            # Get API key for testing
            api_key = Config.get_gemini_api_key() or "test-api-key"

            # Test RAG service creation and destruction
            rag_memory_samples = []

            for i in range(5):
                # Create RAG service
                rag_service = EnhancedRAGService(
                    api_key=api_key,
                    test_mode=True,  # Use test mode
                    vector_storage_dir=str(Path.home() / ".ai_pdf_scholar" / "test_vectors")
                )

                # Use service briefly
                try:
                    # Test basic functionality without actual API calls
                    info = rag_service.get_service_info()
                    print(f"   RAG Service {i+1}: {info.get('status', 'unknown')}")
                except Exception as e:
                    print(f"   RAG Service {i+1}: error - {e}")

                # Clean up
                del rag_service
                gc.collect()

                current_memory = process.memory_info().rss / 1024 / 1024
                rag_memory_samples.append(current_memory)

                time.sleep(0.1)

            rag_growth = rag_memory_samples[-1] - rag_memory_samples[0]
            avg_rag_growth = rag_growth / len(rag_memory_samples)

            print("\n   📊 RAG Service Memory Analysis:")
            print(f"   - Total growth: {rag_growth:.3f} MB")
            print(f"   - Average per operation: {avg_rag_growth:.3f} MB")

        except Exception as e:
            print(f"   ⚠️  RAG service test failed: {e}")

        # Get memory tracing snapshot
        print("\n3. Memory allocation analysis...")
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')

        print("   📋 Top 10 memory allocations:")
        for index, stat in enumerate(top_stats[:10], 1):
            print(f"   {index:2d}. {stat}")

        # Overall memory summary
        final_memory = process.memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory

        print("\n🎯 Memory Analysis Summary:")
        print(f"   Initial: {initial_memory:.2f} MB")
        print(f"   Final: {final_memory:.2f} MB")
        print(f"   Growth: {total_growth:.2f} MB")

        if total_growth > 50:  # 50MB growth is concerning
            print("   ⚠️  Significant memory growth detected")
            return False
        else:
            print("   ✅ Memory usage within acceptable range")
            return True

    except Exception as e:
        print(f"❌ Memory analysis failed: {e}")
        traceback.print_exc()
        return False

    finally:
        tracemalloc.stop()

def optimize_memory_settings():
    """Apply memory optimization settings."""
    print("\n🔧 Applying Memory Optimizations")
    print("=" * 50)

    try:
        # Optimize Python garbage collection
        import gc

        # Get current GC settings
        old_thresholds = gc.get_threshold()
        print(f"Current GC thresholds: {old_thresholds}")

        # Set more aggressive garbage collection for web service
        # Reduce thresholds to collect more frequently
        new_thresholds = (500, 8, 8)  # More frequent collection
        gc.set_threshold(*new_thresholds)

        print(f"New GC thresholds: {gc.get_threshold()}")

        # Enable debug flags for tracking (development only)
        if __debug__:
            gc.set_debug(gc.DEBUG_STATS)

        # Force immediate collection
        collected = gc.collect()
        print(f"Immediate garbage collection freed: {collected} objects")

        # Apply SQLite memory optimizations
        print("\n📚 Database Memory Optimizations:")

        # Test optimized database settings
        from src.database.connection import DatabaseConnection

        db_path = Path.home() / ".ai_pdf_scholar" / "documents.db"
        if db_path.exists():
            db = DatabaseConnection(str(db_path))

            # Apply SQLite memory optimizations
            with db.get_cursor() as cursor:
                # Set aggressive memory limits
                cursor.execute("PRAGMA cache_size = -16000")  # 16MB cache
                cursor.execute("PRAGMA temp_store = MEMORY")   # Use memory for temp
                cursor.execute("PRAGMA mmap_size = 67108864")  # 64MB mmap
                cursor.execute("PRAGMA journal_mode = WAL")    # WAL for better concurrency

                # Get current settings
                cache_size = cursor.execute("PRAGMA cache_size").fetchone()[0]
                temp_store = cursor.execute("PRAGMA temp_store").fetchone()[0]
                journal_mode = cursor.execute("PRAGMA journal_mode").fetchone()[0]

                print(f"   Cache size: {cache_size} pages")
                print(f"   Temp store: {'MEMORY' if temp_store == 2 else 'FILE'}")
                print(f"   Journal mode: {journal_mode}")

            db.close_all_connections()
            print("   ✅ Database optimizations applied")
        else:
            print("   📝 Database not found, optimizations will apply on creation")

        print("\n✅ Memory optimizations completed successfully")
        return True

    except Exception as e:
        print(f"❌ Memory optimization failed: {e}")
        traceback.print_exc()
        return False

def create_memory_monitoring():
    """Create memory monitoring configuration."""
    print("\n📊 Setting up Memory Monitoring")
    print("=" * 50)

    try:
        # Create memory monitoring configuration
        monitoring_config = {
            "memory_monitoring": {
                "enabled": True,
                "warning_threshold_mb": 1024,  # 1GB
                "critical_threshold_mb": 2048, # 2GB
                "check_interval_seconds": 30,
                "log_memory_usage": True,
                "gc_on_threshold": True
            },
            "database_connection": {
                "max_connections": 10,
                "connection_timeout": 30,
                "idle_timeout": 300,
                "cleanup_interval": 60
            },
            "rag_service": {
                "memory_limit_mb": 512,
                "vector_cache_size": 100,
                "index_memory_mapping": True
            }
        }

        # Save monitoring configuration
        config_path = Path("memory_monitoring_config.json")

        import json
        with open(config_path, 'w') as f:
            json.dump(monitoring_config, f, indent=2)

        print(f"   ✅ Memory monitoring config saved to: {config_path}")

        # Create memory monitoring script
        monitoring_script = '''#!/usr/bin/env python3
"""
Memory Monitoring Service

Monitors memory usage and applies optimizations automatically.
"""

import psutil
import time
import logging
import gc
from pathlib import Path

def monitor_memory():
    """Monitor memory usage continuously."""
    process = psutil.Process()

    while True:
        memory_mb = process.memory_info().rss / 1024 / 1024

        if memory_mb > 2048:  # 2GB critical threshold
            logging.critical(f"Critical memory usage: {memory_mb:.1f}MB")
            gc.collect()  # Force garbage collection
        elif memory_mb > 1024:  # 1GB warning threshold
            logging.warning(f"High memory usage: {memory_mb:.1f}MB")

        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    monitor_memory()
'''

        script_path = Path("memory_monitor.py")
        with open(script_path, 'w') as f:
            f.write(monitoring_script)

        print(f"   ✅ Memory monitoring script created: {script_path}")

        return True

    except Exception as e:
        print(f"❌ Memory monitoring setup failed: {e}")
        return False

def main():
    """Main optimization function."""
    print("🚀 AI Enhanced PDF Scholar - Memory Optimization")
    print("=" * 60)

    # Run analysis
    analysis_success = analyze_memory_usage()

    # Apply optimizations
    optimization_success = optimize_memory_settings()

    # Set up monitoring
    monitoring_success = create_memory_monitoring()

    print("\n" + "=" * 60)
    print("🎯 Memory Optimization Summary:")
    print(f"   Analysis: {'✅ PASSED' if analysis_success else '❌ FAILED'}")
    print(f"   Optimization: {'✅ APPLIED' if optimization_success else '❌ FAILED'}")
    print(f"   Monitoring: {'✅ CONFIGURED' if monitoring_success else '❌ FAILED'}")

    if all([analysis_success, optimization_success, monitoring_success]):
        print("\n🎉 Memory optimization completed successfully!")
        print("💡 Recommendations:")
        print("   1. Monitor memory usage in production")
        print("   2. Run garbage collection periodically")
        print("   3. Set memory limits for RAG operations")
        print("   4. Use connection pooling efficiently")
    else:
        print("\n⚠️  Memory optimization partially completed")
        print("   Some issues require manual intervention")

if __name__ == "__main__":
    main()
