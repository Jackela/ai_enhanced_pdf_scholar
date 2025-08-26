#!/usr/bin/env python3
"""
Database Performance Benchmark Script
Comprehensive testing and analysis of database performance optimizations.
Tests query performance, index effectiveness, and provides optimization recommendations.
"""

import argparse
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    # Add parent directory to path
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.database.connection import DatabaseConnection
    from src.database.models import CitationModel, DocumentModel, VectorIndexModel
    from src.database.modular_migrator import (
        ModularDatabaseMigrator as DatabaseMigrator,
    )
    from src.repositories.citation_repository import CitationRepository
    from src.repositories.document_repository import DocumentRepository
    from src.repositories.vector_repository import VectorIndexRepository
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure you're running from the project root directory")
    exit(1)


class DatabasePerformanceBenchmark:
    """
    Comprehensive database performance benchmark suite.
    Tests various aspects of database performance including:
    - Index effectiveness
    - Query performance
    - Optimization recommendations
    - Performance regression detection
    """

    def __init__(self, db_path: str | None = None):
        """
        Initialize the benchmark suite.
        Args:
            db_path: Path to database file (creates temporary if None)
        """
        if db_path:
            self.db_path = db_path
            self.cleanup_db = False
        else:
            self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            self.db_path = self.temp_file.name
            self.cleanup_db = True

        self.db = DatabaseConnection(self.db_path)
        self.migrator = DatabaseMigrator(self.db)

        # Initialize repositories
        self.doc_repo = DocumentRepository(self.db)
        self.citation_repo = CitationRepository(self.db)
        self.vector_repo = VectorIndexRepository(self.db)

        self.benchmark_results = {
            "database_path": self.db_path,
            "schema_version": 0,
            "test_timestamp": time.time(),
            "performance_tests": {},
            "index_analysis": {},
            "optimization_recommendations": [],
            "baseline_comparisons": {},
        }

    def setup_test_environment(self):
        """Setup the test environment with schema and sample data."""
        logger.info("Setting up test environment...")

        # Ensure database is migrated to latest version
        if self.migrator.needs_migration():
            logger.info("Migrating database to latest version...")
            success = self.migrator.migrate()
            if not success:
                raise RuntimeError("Database migration failed")

        self.benchmark_results["schema_version"] = self.migrator.get_current_version()

        # Create sample data for testing
        self._create_sample_data()

        logger.info("Test environment setup completed")

    def _create_sample_data(self):
        """Create sample data for performance testing."""
        logger.info("Creating sample test data...")

        # Sample documents
        sample_documents = []
        for i in range(100):
            doc = DocumentModel(
                id=None,
                title=f"Test Document {i+1:03d}",
                file_path=f"/test/documents/doc_{i+1:03d}.pdf",
                file_hash=f"hash_{i+1:032d}",
                content_hash=f"content_hash_{i+1:032d}" if i % 2 == 0 else None,
                file_size=1024 * (i + 1) * 10,  # Varying file sizes
                page_count=5 + (i % 20),  # 5-24 pages
                created_at=None,  # Will be set by database
                updated_at=None,
                last_accessed=None if i % 3 == 0 else None,  # Some have access times
                metadata={"test": True, "category": f"category_{i % 5}"}
            )
            created_doc = self.doc_repo.create(doc)
            sample_documents.append(created_doc)

        # Sample citations
        for i, doc in enumerate(sample_documents[:50]):  # Only first 50 docs have citations
            citation_count = 1 + (i % 3)  # 1-3 citations per document
            for j in range(citation_count):
                citation = CitationModel(
                    id=None,
                    document_id=doc.id,
                    raw_text=f"Sample citation {j+1} for document {doc.id}",
                    authors=f"Author {j+1}, Author {j+2}" if j % 2 == 0 else f"Single Author {j+1}",
                    title=f"Citation Title {j+1}",
                    publication_year=2020 + (j % 4),
                    journal_or_venue=f"Journal {j+1}",
                    doi=f"10.1000/test.{doc.id}.{j+1}" if j % 2 == 0 else None,
                    citation_type="journal" if j % 2 == 0 else "conference",
                    confidence_score=0.7 + (j % 3) * 0.1,  # 0.7, 0.8, 0.9
                )
                self.citation_repo.create(citation)

        # Sample vector indexes
        for i, doc in enumerate(sample_documents[:30]):  # Only first 30 docs have vector indexes
            vector_index = VectorIndexModel(
                id=None,
                document_id=doc.id,
                index_path=f"/test/indexes/index_{doc.id}",
                index_hash=f"index_hash_{doc.id:032d}",
                chunk_count=10 + (i % 20),
            )
            self.vector_repo.create(vector_index)

        logger.info(f"Created sample data: {len(sample_documents)} documents, citations, and vector indexes")

    def run_query_performance_tests(self) -> dict[str, Any]:
        """Run comprehensive query performance tests."""
        logger.info("Running query performance tests...")

        test_queries = [
            # Basic document queries
            ("simple_count", "SELECT COUNT(*) FROM documents", ()),
            ("recent_documents", "SELECT * FROM documents ORDER BY created_at DESC LIMIT 10", ()),
            ("large_documents", "SELECT * FROM documents WHERE file_size > ? ORDER BY file_size DESC LIMIT 10", (50000,)),

            # Search queries
            ("title_search", "SELECT * FROM documents WHERE title LIKE ? ORDER BY title LIMIT 10", ("%Test%",)),
            ("content_hash_lookup", "SELECT * FROM documents WHERE content_hash = ?", ("content_hash_000000000000000000000002",)),
            ("file_hash_lookup", "SELECT * FROM documents WHERE file_hash = ?", ("hash_000000000000000000000005",)),

            # Join queries
            ("document_citations", "SELECT d.*, COUNT(c.id) as citation_count FROM documents d LEFT JOIN citations c ON d.id = c.document_id GROUP BY d.id ORDER BY citation_count DESC LIMIT 10", ()),
            ("document_with_indexes", "SELECT d.*, vi.chunk_count FROM documents d JOIN vector_indexes vi ON d.id = vi.document_id ORDER BY vi.chunk_count DESC LIMIT 10", ()),

            # Complex analytical queries
            ("citation_analysis", "SELECT c.publication_year, COUNT(*) as count, AVG(c.confidence_score) as avg_confidence FROM citations c WHERE c.confidence_score >= ? GROUP BY c.publication_year ORDER BY c.publication_year DESC", (0.8,)),
            ("document_size_stats", "SELECT AVG(file_size) as avg_size, MIN(file_size) as min_size, MAX(file_size) as max_size, COUNT(*) as count FROM documents", ()),

            # Date range queries
            ("recent_activity", "SELECT * FROM documents WHERE created_at >= datetime('now', '-7 days') ORDER BY created_at DESC", ()),
            ("access_analytics", "SELECT * FROM documents WHERE last_accessed IS NOT NULL ORDER BY last_accessed DESC LIMIT 20", ()),
        ]

        # Benchmark queries
        benchmark_results = self.migrator.benchmark_query_performance(test_queries)

        # Add detailed analysis for key queries
        detailed_analyses = {}
        key_queries = [
            ("title_search", "SELECT * FROM documents WHERE title LIKE ? ORDER BY title LIMIT 10", ("%Test%",)),
            ("document_citations", "SELECT d.*, COUNT(c.id) as citation_count FROM documents d LEFT JOIN citations c ON d.id = c.document_id GROUP BY d.id ORDER BY citation_count DESC LIMIT 10", ()),
        ]

        for query_name, query_sql, params in key_queries:
            detailed_analyses[query_name] = self.migrator.get_advanced_query_analysis(query_sql, params)

        benchmark_results["detailed_analyses"] = detailed_analyses

        self.benchmark_results["performance_tests"] = benchmark_results
        logger.info(f"Query performance tests completed. Fastest: {benchmark_results.get('fastest_query', 'unknown')}, Slowest: {benchmark_results.get('slowest_query', 'unknown')}")

        return benchmark_results

    def run_index_effectiveness_analysis(self) -> dict[str, Any]:
        """Analyze the effectiveness of database indexes."""
        logger.info("Analyzing index effectiveness...")

        # Get comprehensive index analysis
        index_analysis = self.migrator.analyze_index_effectiveness()

        # Get detailed index usage statistics
        index_stats = self.migrator._get_index_usage_statistics()

        # Combine analyses
        comprehensive_analysis = {
            "effectiveness_analysis": index_analysis,
            "usage_statistics": index_stats,
            "performance_impact": self._assess_index_performance_impact(),
        }

        self.benchmark_results["index_analysis"] = comprehensive_analysis
        logger.info(f"Index analysis completed. Found {len(index_stats)} indexes")

        return comprehensive_analysis

    def _assess_index_performance_impact(self) -> dict[str, Any]:
        """Assess the performance impact of indexes by testing with/without scenarios."""
        logger.info("Assessing index performance impact...")

        # Test some queries that should benefit significantly from indexes
        impact_tests = [
            {
                "test_name": "file_hash_lookup_impact",
                "description": "File hash lookup performance with index",
                "query": "SELECT * FROM documents WHERE file_hash = ?",
                "params": ("hash_000000000000000000000010",),
                "expected_index": "idx_documents_file_hash_unique",
            },
            {
                "test_name": "recent_documents_impact",
                "description": "Recent documents query with temporal index",
                "query": "SELECT * FROM documents ORDER BY created_at DESC LIMIT 10",
                "params": (),
                "expected_index": "idx_documents_created_desc_perf",
            },
            {
                "test_name": "citation_lookup_impact",
                "description": "Citation lookup by document with foreign key index",
                "query": "SELECT * FROM citations WHERE document_id = ?",
                "params": (5,),
                "expected_index": "idx_citations_document_perf",
            },
        ]

        impact_results = []

        for test in impact_tests:
            # Get execution plan and timing
            execution_plan = self.migrator.get_query_execution_plan(test["query"])

            # Time the query
            start_time = time.time()
            if test["params"]:
                results = self.db.fetch_all(test["query"], test["params"])
            else:
                results = self.db.fetch_all(test["query"])
            execution_time = (time.time() - start_time) * 1000

            # Check if expected index is used
            plan_text = " ".join([step.get("detail", "") for step in execution_plan])
            index_used = test["expected_index"] in plan_text

            impact_result = {
                "test_name": test["test_name"],
                "description": test["description"],
                "execution_time_ms": execution_time,
                "rows_returned": len(results),
                "expected_index": test["expected_index"],
                "index_used": index_used,
                "execution_plan": execution_plan,
                "performance_rating": "excellent" if execution_time < 1 and index_used else
                                   "good" if execution_time < 10 and index_used else
                                   "poor" if not index_used else "fair"
            }

            impact_results.append(impact_result)
            logger.debug(f"Index impact test '{test['test_name']}': {execution_time:.2f}ms, index used: {index_used}")

        return {
            "impact_tests": impact_results,
            "overall_index_health": self._calculate_overall_index_health(impact_results),
        }

    def _calculate_overall_index_health(self, impact_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate overall index health based on impact test results."""
        total_tests = len(impact_results)
        if total_tests == 0:
            return {"score": 0, "rating": "unknown"}

        excellent_count = sum(1 for test in impact_results if test["performance_rating"] == "excellent")
        good_count = sum(1 for test in impact_results if test["performance_rating"] == "good")
        fair_count = sum(1 for test in impact_results if test["performance_rating"] == "fair")
        poor_count = sum(1 for test in impact_results if test["performance_rating"] == "poor")

        # Calculate weighted score
        score = (excellent_count * 4 + good_count * 3 + fair_count * 2 + poor_count * 1) / (total_tests * 4)

        if score >= 0.9:
            rating = "excellent"
        elif score >= 0.7:
            rating = "good"
        elif score >= 0.5:
            rating = "fair"
        else:
            rating = "poor"

        return {
            "score": score,
            "rating": rating,
            "test_breakdown": {
                "excellent": excellent_count,
                "good": good_count,
                "fair": fair_count,
                "poor": poor_count,
            },
        }

    def run_performance_regression_tests(self) -> dict[str, Any]:
        """Run performance regression tests against baselines."""
        logger.info("Running performance regression tests...")

        # Get current performance baselines
        try:
            baselines = self.db.fetch_all(
                "SELECT metric_name, baseline_value, measurement_unit FROM performance_baselines ORDER BY measured_at DESC"
            )
            baseline_dict = {b["metric_name"]: b["baseline_value"] for b in baselines}
        except:
            logger.warning("No performance baselines found. This may be the first run.")
            baseline_dict = {}

        # Current measurements
        current_measurements = {}

        # Re-measure key metrics
        try:
            # Table row counts
            for table in ['documents', 'vector_indexes', 'citations']:
                count_result = self.db.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                current_measurements[f"table_row_count_{table}"] = count_result['count'] if count_result else 0

            # Sample query timings
            sample_queries = [
                ("simple_count_documents", "SELECT COUNT(*) FROM documents"),
                ("recent_documents_query", "SELECT * FROM documents ORDER BY created_at DESC LIMIT 10"),
            ]

            for query_name, query in sample_queries:
                start_time = time.time()
                self.db.fetch_all(query)
                execution_time = (time.time() - start_time) * 1000
                current_measurements[f"query_time_{query_name}"] = execution_time

        except Exception as e:
            logger.warning(f"Error measuring current performance: {e}")

        # Compare with baselines
        regression_results = {
            "baseline_comparison": {},
            "regressions_detected": [],
            "improvements_detected": [],
            "new_metrics": [],
        }

        for metric_name, current_value in current_measurements.items():
            if metric_name in baseline_dict:
                baseline_value = baseline_dict[metric_name]
                if baseline_value > 0:  # Avoid division by zero
                    change_ratio = current_value / baseline_value
                    change_percent = (change_ratio - 1) * 100

                    comparison = {
                        "metric": metric_name,
                        "baseline": baseline_value,
                        "current": current_value,
                        "change_percent": change_percent,
                        "change_ratio": change_ratio,
                    }

                    # Detect significant changes (more than 20% for performance metrics)
                    if "query_time" in metric_name and change_percent > 20:
                        regression_results["regressions_detected"].append(comparison)
                    elif "query_time" in metric_name and change_percent < -20:
                        regression_results["improvements_detected"].append(comparison)

                    regression_results["baseline_comparison"][metric_name] = comparison
            else:
                regression_results["new_metrics"].append({
                    "metric": metric_name,
                    "current": current_value,
                })

        self.benchmark_results["baseline_comparisons"] = regression_results
        logger.info(f"Regression tests completed. Found {len(regression_results['regressions_detected'])} regressions, {len(regression_results['improvements_detected'])} improvements")

        return regression_results

    def generate_optimization_recommendations(self) -> list[str]:
        """Generate comprehensive optimization recommendations."""
        logger.info("Generating optimization recommendations...")

        recommendations = []

        # Analyze performance test results
        if "performance_tests" in self.benchmark_results:
            perf_results = self.benchmark_results["performance_tests"]

            # Check for slow queries
            if "benchmarks" in perf_results:
                slow_queries = [b for b in perf_results["benchmarks"] if b["average_time_ms"] > 50]
                if slow_queries:
                    recommendations.append(f"Found {len(slow_queries)} queries taking >50ms. Consider optimization.")
                    for query in slow_queries[:3]:  # Show top 3 slowest
                        recommendations.append(f"  - {query['query_name']}: {query['average_time_ms']:.2f}ms")

        # Analyze index effectiveness
        if "index_analysis" in self.benchmark_results:
            index_analysis = self.benchmark_results["index_analysis"]

            if "effectiveness_analysis" in index_analysis:
                effectiveness = index_analysis["effectiveness_analysis"]

                # Check index effectiveness ratio
                if "summary" in effectiveness and effectiveness["summary"].get("index_effectiveness_ratio", 0) < 0.6:
                    recommendations.append("Index effectiveness is below optimal. Consider adding more targeted indexes.")

                # Check for potentially unused indexes
                if effectiveness.get("potentially_unused"):
                    recommendations.append(f"Monitor {len(effectiveness['potentially_unused'])} potentially unused indexes for removal.")

        # Check performance impact
        if "index_analysis" in self.benchmark_results and "performance_impact" in self.benchmark_results["index_analysis"]:
            impact = self.benchmark_results["index_analysis"]["performance_impact"]

            if "overall_index_health" in impact:
                health = impact["overall_index_health"]
                if health["score"] < 0.7:
                    recommendations.append(f"Index performance health is {health['rating']} ({health['score']:.2f}). Review index usage.")

        # Check for regressions
        if "baseline_comparisons" in self.benchmark_results:
            regressions = self.benchmark_results["baseline_comparisons"]["regressions_detected"]
            if regressions:
                recommendations.append(f"Detected {len(regressions)} performance regressions. Investigate recent changes.")

        # General recommendations
        recommendations.extend([
            "Run VACUUM periodically to reclaim space and optimize file layout",
            "Monitor query performance in production and update indexes as needed",
            "Consider archiving old data if tables grow beyond 100K rows",
            "Regular ANALYZE execution helps maintain optimal query plans",
        ])

        self.benchmark_results["optimization_recommendations"] = recommendations
        logger.info(f"Generated {len(recommendations)} optimization recommendations")

        return recommendations

    def run_full_benchmark_suite(self) -> dict[str, Any]:
        """Run the complete benchmark suite."""
        logger.info("Starting full database performance benchmark suite...")

        try:
            # Setup test environment
            self.setup_test_environment()

            # Run all benchmark components
            self.run_query_performance_tests()
            self.run_index_effectiveness_analysis()
            self.run_performance_regression_tests()
            self.generate_optimization_recommendations()

            # Add summary information
            self.benchmark_results["summary"] = {
                "total_tests_run": len(self.benchmark_results.get("performance_tests", {}).get("benchmarks", [])),
                "total_indexes_analyzed": len(self.benchmark_results.get("index_analysis", {}).get("usage_statistics", [])),
                "recommendations_generated": len(self.benchmark_results.get("optimization_recommendations", [])),
                "overall_performance_score": self._calculate_overall_performance_score(),
            }

            logger.info("Full benchmark suite completed successfully")

        except Exception as e:
            logger.error(f"Benchmark suite failed: {e}")
            self.benchmark_results["error"] = str(e)
            raise

        return self.benchmark_results

    def _calculate_overall_performance_score(self) -> float:
        """Calculate overall performance score (0-100)."""
        score_components = []

        # Query performance component
        if "performance_tests" in self.benchmark_results:
            perf_data = self.benchmark_results["performance_tests"]
            if "average_time" in perf_data and perf_data["average_time"] > 0:
                # Score based on average query time (lower is better)
                avg_time = perf_data["average_time"]
                time_score = max(0, 100 - (avg_time - 1) * 2)  # Penalize times > 1ms
                score_components.append(min(100, max(0, time_score)))

        # Index health component
        if "index_analysis" in self.benchmark_results:
            index_data = self.benchmark_results["index_analysis"]
            if "performance_impact" in index_data and "overall_index_health" in index_data["performance_impact"]:
                health_score = index_data["performance_impact"]["overall_index_health"]["score"] * 100
                score_components.append(health_score)

        # Regression component (penalize regressions)
        regression_penalty = 0
        if "baseline_comparisons" in self.benchmark_results:
            regressions = len(self.benchmark_results["baseline_comparisons"]["regressions_detected"])
            regression_penalty = regressions * 10  # 10 points per regression

        # Calculate final score
        if score_components:
            base_score = sum(score_components) / len(score_components)
            final_score = max(0, base_score - regression_penalty)
        else:
            final_score = 50  # Default score if no components available

        return round(final_score, 2)

    def save_results(self, output_file: str):
        """Save benchmark results to JSON file."""
        try:
            with open(output_file, 'w') as f:
                json.dump(self.benchmark_results, f, indent=2, default=str)
            logger.info(f"Benchmark results saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save results to {output_file}: {e}")
            raise

    def print_summary(self):
        """Print a summary of benchmark results."""
        print("\n" + "="*80)
        print("DATABASE PERFORMANCE BENCHMARK SUMMARY")
        print("="*80)

        # Basic info
        print(f"Database: {self.benchmark_results['database_path']}")
        print(f"Schema Version: {self.benchmark_results['schema_version']}")
        print(f"Benchmark Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.benchmark_results['test_timestamp']))}")

        # Summary stats
        if "summary" in self.benchmark_results:
            summary = self.benchmark_results["summary"]
            print(f"\nOverall Performance Score: {summary.get('overall_performance_score', 'N/A')}/100")
            print(f"Tests Run: {summary.get('total_tests_run', 0)}")
            print(f"Indexes Analyzed: {summary.get('total_indexes_analyzed', 0)}")
            print(f"Recommendations: {summary.get('recommendations_generated', 0)}")

        # Performance highlights
        if "performance_tests" in self.benchmark_results:
            perf = self.benchmark_results["performance_tests"]
            print("\nQuery Performance:")
            print(f"  Average Query Time: {perf.get('average_time', 'N/A'):.2f}ms")
            print(f"  Fastest Query: {perf.get('fastest_query', 'N/A')}")
            print(f"  Slowest Query: {perf.get('slowest_query', 'N/A')}")

        # Index health
        if "index_analysis" in self.benchmark_results:
            index_data = self.benchmark_results["index_analysis"]
            if "performance_impact" in index_data and "overall_index_health" in index_data["performance_impact"]:
                health = index_data["performance_impact"]["overall_index_health"]
                print(f"\nIndex Health: {health['rating'].upper()} ({health['score']:.2f})")

        # Key recommendations
        if "optimization_recommendations" in self.benchmark_results:
            recommendations = self.benchmark_results["optimization_recommendations"]
            print("\nTop Recommendations:")
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"  {i}. {rec}")

        print("\n" + "="*80)

    def cleanup(self):
        """Cleanup resources."""
        try:
            if hasattr(self, 'db'):
                self.db.close_all_connections()

            if self.cleanup_db and Path(self.db_path).exists():
                Path(self.db_path).unlink()
                logger.debug(f"Cleaned up temporary database: {self.db_path}")

        except Exception as e:
            logger.warning(f"Cleanup error: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(description="Database Performance Benchmark Tool")
    parser.add_argument("--db-path", help="Path to database file (creates temporary if not specified)")
    parser.add_argument("--output", "-o", help="Output file for results (JSON format)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--quick", action="store_true", help="Run only essential tests (faster)")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        with DatabasePerformanceBenchmark(args.db_path) as benchmark:
            # Run benchmark suite
            if args.quick:
                logger.info("Running quick benchmark (query performance only)...")
                benchmark.setup_test_environment()
                benchmark.run_query_performance_tests()
                benchmark.generate_optimization_recommendations()
            else:
                logger.info("Running full benchmark suite...")
                benchmark.run_full_benchmark_suite()

            # Print summary
            benchmark.print_summary()

            # Save results if requested
            if args.output:
                benchmark.save_results(args.output)

            return 0

    except KeyboardInterrupt:
        logger.info("Benchmark interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
