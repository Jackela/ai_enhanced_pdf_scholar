#!/usr/bin/env python3
"""
Quick test script to validate database performance optimizations.
Tests the new migration 005 and performance monitoring features.
"""

import logging
import tempfile
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    from src.database.connection import DatabaseConnection
    from src.database.models import DocumentModel
    from src.database.modular_migrator import (
        ModularDatabaseMigrator as DatabaseMigrator,
    )
    from src.repositories.document_repository import DocumentRepository
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure you're running from the project root directory")
    exit(1)


def test_migration_005():
    """Test migration 005 performance optimization features."""
    logger.info("Testing migration 005 performance optimization...")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        # Initialize database and migrator
        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)

        # Check initial state
        initial_version = migrator.get_current_version()
        logger.info(f"Initial database version: {initial_version}")

        # Run migration to latest version (should include migration 005)
        if migrator.needs_migration():
            logger.info("Running migration to latest version...")
            success = migrator.migrate()
            if not success:
                logger.error("Migration failed!")
                return False

        final_version = migrator.get_current_version()
        logger.info(f"Final database version: {final_version}")

        # Check if migration 005 features are available
        if final_version >= 5:
            logger.info("✅ Migration 005 completed successfully")

            # Test performance monitoring tables
            test_tables = [
                "query_performance_log",
                "index_usage_stats",
                "performance_baselines",
            ]

            for table in test_tables:
                try:
                    result = db.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                    logger.info(
                        f"✅ Performance monitoring table '{table}' created (rows: {result['count'] if result else 0})"
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Performance monitoring table '{table}' not found: {e}"
                    )
                    return False

            # Test advanced performance analysis functions
            try:
                stats = migrator.get_performance_statistics()
                logger.info(
                    f"✅ Performance statistics available: {len(stats)} categories"
                )
            except Exception as e:
                logger.error(f"❌ Performance statistics function failed: {e}")
                return False

            # Test index effectiveness analysis
            try:
                index_analysis = migrator.analyze_index_effectiveness()
                total_indexes = index_analysis.get("total_indexes", 0)
                logger.info(
                    f"✅ Index effectiveness analysis available: {total_indexes} indexes analyzed"
                )
            except Exception as e:
                logger.error(f"❌ Index effectiveness analysis failed: {e}")
                return False

            return True
        else:
            logger.error(
                f"❌ Migration 005 not applied. Current version: {final_version}"
            )
            return False

    finally:
        # Cleanup
        db.close_all_connections()
        Path(db_path).unlink(missing_ok=True)


def test_query_performance_analysis():
    """Test query performance analysis features."""
    logger.info("Testing query performance analysis...")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        doc_repo = DocumentRepository(db)

        # Migrate to latest version
        migrator.migrate()

        # Create some test data
        logger.info("Creating test data...")
        for i in range(10):
            doc = DocumentModel(
                id=None,
                title=f"Test Document {i+1}",
                file_path=f"/test/doc_{i+1}.pdf",
                file_hash=f"hash_{i+1:032d}",
                file_size=1024 * (i + 1),
                page_count=5 + i,
            )
            doc_repo.create(doc)

        # Test various query analysis features
        test_queries = [
            ("simple_select", "SELECT * FROM documents LIMIT 5", ()),
            ("title_search", "SELECT * FROM documents WHERE title LIKE ?", ("%Test%",)),
            (
                "size_filter",
                "SELECT * FROM documents WHERE file_size > ? ORDER BY file_size DESC",
                (5000,),
            ),
        ]

        for query_name, query, params in test_queries:
            try:
                # Test execution plan analysis
                execution_plan = migrator.get_query_execution_plan(query)
                logger.info(
                    f"✅ Execution plan for '{query_name}': {len(execution_plan)} steps"
                )

                # Test advanced query analysis
                analysis = migrator.get_advanced_query_analysis(query, params)
                execution_time = analysis.get("performance_metrics", {}).get(
                    "execution_time_ms", 0
                )
                recommendations = len(analysis.get("optimization_recommendations", []))
                logger.info(
                    f"✅ Advanced analysis for '{query_name}': {execution_time:.2f}ms, {recommendations} recommendations"
                )

            except Exception as e:
                logger.error(f"❌ Query analysis failed for '{query_name}': {e}")
                return False

        # Test benchmark functionality
        try:
            benchmark_results = migrator.benchmark_query_performance(test_queries)
            total_benchmarks = len(benchmark_results.get("benchmarks", []))
            fastest_query = benchmark_results.get("fastest_query", "unknown")
            logger.info(
                f"✅ Query benchmarking: {total_benchmarks} queries tested, fastest: {fastest_query}"
            )
        except Exception as e:
            logger.error(f"❌ Query benchmarking failed: {e}")
            return False

        return True

    finally:
        db.close_all_connections()
        Path(db_path).unlink(missing_ok=True)


def test_index_analysis():
    """Test index analysis and optimization features."""
    logger.info("Testing index analysis features...")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)

        # Migrate to latest version (includes all performance indexes)
        migrator.migrate()

        # Test index usage statistics
        try:
            index_stats = migrator._get_index_usage_statistics()
            logger.info(f"✅ Index usage statistics: {len(index_stats)} indexes found")
        except Exception as e:
            logger.error(f"❌ Index usage statistics failed: {e}")
            return False

        # Test index effectiveness analysis
        try:
            effectiveness = migrator.analyze_index_effectiveness()
            total_indexes = effectiveness.get("total_indexes", 0)
            high_impact = len(effectiveness.get("high_impact", []))
            logger.info(
                f"✅ Index effectiveness analysis: {total_indexes} total, {high_impact} high-impact"
            )
        except Exception as e:
            logger.error(f"❌ Index effectiveness analysis failed: {e}")
            return False

        # Test slow query analysis
        try:
            slow_analysis = migrator.analyze_slow_queries()
            potential_slow = len(slow_analysis.get("potential_slow_queries", []))
            suggestions = len(slow_analysis.get("optimization_suggestions", []))
            logger.info(
                f"✅ Slow query analysis: {potential_slow} potential issues, {suggestions} suggestions"
            )
        except Exception as e:
            logger.error(f"❌ Slow query analysis failed: {e}")
            return False

        return True

    finally:
        db.close_all_connections()
        Path(db_path).unlink(missing_ok=True)


def test_database_optimization():
    """Test database optimization functions."""
    logger.info("Testing database optimization features...")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)

        # Migrate to latest version
        migrator.migrate()

        # Test database optimization
        try:
            optimization_results = migrator.optimize_database_performance()
            operations = len(optimization_results.get("operations_performed", []))
            success = optimization_results.get("success", False)
            logger.info(
                f"✅ Database optimization: {operations} operations, success: {success}"
            )
        except Exception as e:
            logger.error(f"❌ Database optimization failed: {e}")
            return False

        # Test performance statistics
        try:
            perf_stats = migrator.get_performance_statistics()
            categories = len(perf_stats)
            db_size = perf_stats.get("database_info", {}).get("database_size_bytes", 0)
            logger.info(
                f"✅ Performance statistics: {categories} categories, DB size: {db_size} bytes"
            )
        except Exception as e:
            logger.error(f"❌ Performance statistics failed: {e}")
            return False

        return True

    finally:
        db.close_all_connections()
        Path(db_path).unlink(missing_ok=True)


def main():
    """Main test function."""
    logger.info("🚀 Starting database performance optimization tests...")

    tests = [
        ("Migration 005", test_migration_005),
        ("Query Performance Analysis", test_query_performance_analysis),
        ("Index Analysis", test_index_analysis),
        ("Database Optimization", test_database_optimization),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} ---")
        try:
            if test_func():
                logger.info(f"✅ {test_name} PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} ERROR: {e}")

    logger.info(f"\n{'='*60}")
    logger.info(f"TEST RESULTS: {passed}/{total} tests passed")

    if passed == total:
        logger.info(
            "🎉 All tests passed! Database performance optimizations are working correctly."
        )
        return 0
    else:
        logger.error(
            f"💥 {total - passed} tests failed. Please check the implementation."
        )
        return 1


if __name__ == "__main__":
    exit(main())
