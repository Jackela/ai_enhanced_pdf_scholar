#!/usr/bin/env python3
"""
CI Performance Check Script
Lightweight performance validation for CI/CD pipelines.
Validates that performance metrics meet minimum thresholds.
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scripts.performance_regression_detector import PerformanceBaseline
    from scripts.simple_benchmark import SimpleBenchmark
except ImportError as e:
    logger.error(f"Failed to import performance modules: {e}")
    sys.exit(1)


class CIPerformanceCheck:
    """Lightweight performance validation for CI/CD"""

    # Performance thresholds for CI validation
    PERFORMANCE_THRESHOLDS = {
        "database_query_max_ms": 10.0,  # Database queries should be under 10ms
        "file_io_min_mb_s": 1.0,        # File I/O should be at least 1 MB/s
        "text_processing_min_chars_s": 1000000,  # Text processing at least 1M chars/s
        "overall_max_ms": 100.0,        # No operation should exceed 100ms
        "regression_threshold_percent": 50.0,  # Alert on >50% performance degradation
    }

    def __init__(self):
        self.results = {}
        self.violations = []
        self.warnings = []

    def run_quick_benchmarks(self) -> dict[str, Any]:
        """Run quick performance benchmarks suitable for CI"""
        logger.info("Running quick performance benchmarks for CI...")

        try:
            # Run lightweight benchmark with fewer iterations
            benchmark = SimpleBenchmark()

            # Override with smaller test counts for CI speed
            results = {
                "database_queries": [],
                "file_operations": [],
                "text_processing": []
            }

            # Quick database benchmark (10 runs instead of 50)
            db_metrics = benchmark.benchmark_basic_queries(runs=10)
            results["database_queries"] = db_metrics

            # Quick file benchmark (10 runs instead of 30)
            file_metrics = benchmark.benchmark_file_operations(runs=10)
            results["file_operations"] = file_metrics

            # Quick text benchmark (10 runs instead of 50)
            text_metrics = benchmark.benchmark_text_processing(runs=10)
            results["text_processing"] = text_metrics

            # Add metadata
            results["metadata"] = {
                "timestamp": datetime.now().isoformat(),
                "ci_mode": True,
                "reduced_iterations": True
            }

            return results

        except Exception as e:
            logger.error(f"Quick benchmarks failed: {e}")
            raise

    def validate_performance_thresholds(self, results: dict[str, Any]) -> bool:
        """Validate performance results against CI thresholds"""
        logger.info("Validating performance against CI thresholds...")

        passed = True

        # Validate database queries
        if "database_queries" in results:
            for query_result in results["database_queries"]:
                avg_time = query_result.get("avg_ms", 0)
                if avg_time > self.PERFORMANCE_THRESHOLDS["database_query_max_ms"]:
                    self.violations.append(
                        f"Database query '{query_result['operation']}' took {avg_time:.2f}ms "
                        f"(threshold: {self.PERFORMANCE_THRESHOLDS['database_query_max_ms']}ms)"
                    )
                    passed = False

        # Validate file operations
        if "file_operations" in results:
            for file_result in results["file_operations"]:
                throughput = file_result.get("throughput_mb_per_sec", 0)
                if throughput < self.PERFORMANCE_THRESHOLDS["file_io_min_mb_s"]:
                    self.violations.append(
                        f"File operation '{file_result['operation']}' achieved {throughput:.2f} MB/s "
                        f"(threshold: {self.PERFORMANCE_THRESHOLDS['file_io_min_mb_s']} MB/s)"
                    )
                    passed = False

        # Validate text processing
        if "text_processing" in results:
            for text_result in results["text_processing"]:
                throughput = text_result.get("throughput_chars_per_sec", 0)
                if throughput < self.PERFORMANCE_THRESHOLDS["text_processing_min_chars_s"]:
                    self.violations.append(
                        f"Text processing '{text_result['operation']}' achieved {throughput:,.0f} chars/s "
                        f"(threshold: {self.PERFORMANCE_THRESHOLDS['text_processing_min_chars_s']:,} chars/s)"
                    )
                    passed = False

        # Check for any operation exceeding overall maximum
        all_operations = []
        for category in ["database_queries", "file_operations", "text_processing"]:
            if category in results:
                for result in results[category]:
                    avg_time = result.get("avg_ms", 0)
                    all_operations.append((result.get("operation", "unknown"), avg_time))

        for operation, avg_time in all_operations:
            if avg_time > self.PERFORMANCE_THRESHOLDS["overall_max_ms"]:
                self.violations.append(
                    f"Operation '{operation}' took {avg_time:.2f}ms "
                    f"(overall threshold: {self.PERFORMANCE_THRESHOLDS['overall_max_ms']}ms)"
                )
                passed = False

        return passed

    def check_regressions(self, results: dict[str, Any]) -> bool:
        """Check for performance regressions against baselines"""
        logger.info("Checking for performance regressions...")

        baseline_file = Path("performance_baselines.json")
        if not baseline_file.exists():
            logger.warning("No baseline file found, skipping regression check")
            return True

        try:
            detector = PerformanceBaseline(baseline_file)
            regressions = detector.detect_regressions(
                results,
                category="system",
                regression_threshold=self.PERFORMANCE_THRESHOLDS["regression_threshold_percent"]
            )

            if regressions:
                for regression in regressions:
                    if regression.severity == "critical":
                        self.violations.append(f"Critical regression: {regression}")
                    else:
                        self.warnings.append(f"Performance regression: {regression}")

                # Fail CI only on critical regressions
                critical_regressions = [r for r in regressions if r.severity == "critical"]
                return len(critical_regressions) == 0

            return True

        except Exception as e:
            logger.warning(f"Regression check failed: {e}")
            return True  # Don't fail CI on regression check errors

    def run_ci_performance_validation(self) -> bool:
        """Run complete CI performance validation"""
        logger.info("Starting CI performance validation...")
        start_time = time.time()

        try:
            # Run quick benchmarks
            results = self.run_quick_benchmarks()

            # Validate thresholds
            thresholds_passed = self.validate_performance_thresholds(results)

            # Check regressions
            regressions_passed = self.check_regressions(results)

            end_time = time.time()

            # Store results
            self.results = {
                "validation_results": results,
                "thresholds_passed": thresholds_passed,
                "regressions_passed": regressions_passed,
                "violations": self.violations,
                "warnings": self.warnings,
                "duration_seconds": end_time - start_time,
                "timestamp": datetime.now().isoformat()
            }

            overall_passed = thresholds_passed and regressions_passed

            logger.info(f"CI performance validation completed in {end_time - start_time:.2f} seconds")
            logger.info(f"Result: {'PASSED' if overall_passed else 'FAILED'}")

            return overall_passed

        except Exception as e:
            logger.error(f"CI performance validation failed: {e}")
            self.results["error"] = str(e)
            return False

    def print_ci_summary(self):
        """Print CI-friendly performance summary"""
        if "error" in self.results:
            print(f"❌ CI PERFORMANCE VALIDATION FAILED: {self.results['error']}")
            return

        print("\n" + "="*70)
        print("CI PERFORMANCE VALIDATION SUMMARY")
        print("="*70)

        # Basic metrics
        duration = self.results.get("duration_seconds", 0)
        thresholds_passed = self.results.get("thresholds_passed", False)
        regressions_passed = self.results.get("regressions_passed", False)

        print(f"⏱️  Validation Time: {duration:.2f} seconds")
        print(f"🎯 Threshold Check: {'✅ PASSED' if thresholds_passed else '❌ FAILED'}")
        print(f"📈 Regression Check: {'✅ PASSED' if regressions_passed else '❌ FAILED'}")

        # Violations
        violations = self.results.get("violations", [])
        if violations:
            print(f"\n🚨 VIOLATIONS ({len(violations)}):")
            for i, violation in enumerate(violations[:5], 1):  # Show first 5
                print(f"   {i}. {violation}")
            if len(violations) > 5:
                print(f"   ... and {len(violations) - 5} more")

        # Warnings
        warnings = self.results.get("warnings", [])
        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for i, warning in enumerate(warnings[:3], 1):  # Show first 3
                print(f"   {i}. {warning}")
            if len(warnings) > 3:
                print(f"   ... and {len(warnings) - 3} more")

        # Overall result
        overall_passed = thresholds_passed and regressions_passed
        if overall_passed:
            print("\n✅ OVERALL RESULT: PASSED")
            print("   Performance meets all CI requirements")
        else:
            print("\n❌ OVERALL RESULT: FAILED")
            print("   Performance does not meet CI requirements")

        print("="*70)

    def save_ci_results(self, filename: str = "ci_performance_results.json"):
        """Save CI results for artifacts"""
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            logger.info(f"CI results saved to {filename}")
        except Exception as e:
            logger.warning(f"Failed to save CI results: {e}")


def main():
    """Main entry point for CI performance validation"""
    import argparse

    parser = argparse.ArgumentParser(description="CI Performance Validation")
    parser.add_argument("--save-results", action="store_true", help="Save results to JSON file")
    parser.add_argument("--quiet", action="store_true", help="Minimal output for CI")
    parser.add_argument("--thresholds", help="Custom thresholds JSON file")

    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    try:
        validator = CIPerformanceCheck()

        # Load custom thresholds if provided
        if args.thresholds:
            try:
                with open(args.thresholds) as f:
                    custom_thresholds = json.load(f)
                validator.PERFORMANCE_THRESHOLDS.update(custom_thresholds)
                logger.info(f"Loaded custom thresholds from {args.thresholds}")
            except Exception as e:
                logger.warning(f"Failed to load custom thresholds: {e}")

        # Run validation
        passed = validator.run_ci_performance_validation()

        # Print summary (unless in quiet mode)
        if not args.quiet:
            validator.print_ci_summary()

        # Save results if requested
        if args.save_results:
            validator.save_ci_results()

        # Exit with appropriate code
        if passed:
            if not args.quiet:
                print("\n🎉 CI performance validation PASSED")
            return 0
        else:
            if not args.quiet:
                print("\n💥 CI performance validation FAILED")
            else:
                # In quiet mode, still show critical information
                violations = validator.results.get("violations", [])
                if violations:
                    print(f"Performance validation failed with {len(violations)} violations")
            return 1

    except Exception as e:
        logger.error(f"CI performance validation error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
