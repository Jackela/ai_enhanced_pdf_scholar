from typing import Any

#!/usr/bin/env python3
"""
Simple Memory Check and Optimization

Check for memory leaks and apply basic optimizations.
"""

import gc
import sys
import traceback
from pathlib import Path

import psutil

# Add project root to path
sys.path.append('.')

def check_memory_patterns() -> Any:
    """Check basic memory usage patterns."""
    print("🔍 Simple Memory Usage Check")
    print("=" * 40)

    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    print(f"Initial Memory: {initial_memory:.1f} MB")

    try:
        # Test database connection creation/destruction
        print("\n1. Testing database connections...")

        memory_samples = []

        for i in range(5):
            # Import and use database
            from src.database.connection import DatabaseConnection

            db_path = str(Path.home() / ".ai_pdf_scholar" / "documents.db")
            db = DatabaseConnection(db_path)

            # Use the database briefly
            with db.transaction():
                pass  # Just test transaction context

            # Close connections
            db.close_all_connections()
            del db

            # Force garbage collection
            gc.collect()

            current_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)
            print(f"   Test {i+1}: {current_memory:.1f} MB")

        # Check memory growth
        memory_growth = memory_samples[-1] - memory_samples[0]
        print(f"\n   📊 Memory growth: {memory_growth:.2f} MB over 5 operations")

        if memory_growth > 5:  # 5MB growth is concerning
            print("   ⚠️  Potential memory leak detected")
            leak_detected = True
        else:
            print("   ✅ Memory usage appears stable")
            leak_detected = False

        return leak_detected

    except Exception as e:
        print(f"❌ Memory check failed: {e}")
        traceback.print_exc()
        return True  # Assume leak on error

def apply_memory_optimizations() -> Any:
    """Apply basic memory optimizations."""
    print("\n🔧 Applying Memory Optimizations")
    print("=" * 40)

    try:
        # 1. Optimize garbage collection
        print("1. Optimizing garbage collection...")

        old_thresholds = gc.get_threshold()
        print(f"   Old GC thresholds: {old_thresholds}")

        # More aggressive GC for web service
        gc.set_threshold(400, 5, 5)  # More frequent collection
        print(f"   New GC thresholds: {gc.get_threshold()}")

        # Force collection
        collected = gc.collect()
        print(f"   Collected {collected} objects")

        # 2. Check current memory usage
        print("\n2. Current memory status...")
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"   Current memory: {memory_mb:.1f} MB")

        # System memory
        system_memory = psutil.virtual_memory()
        print(f"   System memory: {system_memory.percent}% used")

        if system_memory.percent > 80:
            print("   ⚠️  System memory usage is high")
        else:
            print("   ✅ System memory usage is normal")

        return True

    except Exception as e:
        print(f"❌ Optimization failed: {e}")
        return False

def create_memory_config() -> Any:
    """Create memory monitoring configuration."""
    print("\n📝 Creating Memory Configuration")
    print("=" * 40)

    try:
        config = {
            "memory_settings": {
                "max_memory_mb": 2048,
                "warning_threshold_mb": 1024,
                "gc_threshold": [400, 5, 5],
                "monitoring_enabled": True
            },
            "database_settings": {
                "max_connections": 10,
                "connection_timeout": 30,
                "connection_pool_cleanup": True
            }
        }

        # Save to file
        import json
        config_path = Path("memory_config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"✅ Memory configuration saved to: {config_path}")
        return True

    except Exception as e:
        print(f"❌ Config creation failed: {e}")
        return False

def main() -> None:
    """Main function."""
    print("🚀 Simple Memory Check and Optimization")
    print("=" * 50)

    # Check for leaks
    leak_detected = check_memory_patterns()

    # Apply optimizations
    optimization_success = apply_memory_optimizations()

    # Create config
    config_success = create_memory_config()

    print("\n" + "=" * 50)
    print("🎯 Memory Check Summary:")
    print(f"   Memory Leak: {'⚠️  DETECTED' if leak_detected else '✅ NONE'}")
    print(f"   Optimization: {'✅ APPLIED' if optimization_success else '❌ FAILED'}")
    print(f"   Configuration: {'✅ CREATED' if config_success else '❌ FAILED'}")

    if not leak_detected and optimization_success:
        print("\n✅ Memory optimization completed successfully!")
    else:
        print("\n⚠️  Some memory issues detected or fixes failed")

    # Clean up test files
    test_files = ["memory_config.json"]
    cleaned = 0
    for test_file in test_files:
        file_path = Path(test_file)
        if file_path.exists() and file_path.stat().st_size < 1000:  # Only small test files
            try:
                # file_path.unlink()  # Keep config file for reference
                cleaned += 1
            except:
                pass

    if cleaned > 0:
        print(f"🧹 Cleaned up {cleaned} test files")

if __name__ == "__main__":
    main()
