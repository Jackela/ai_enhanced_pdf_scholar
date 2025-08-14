#!/usr/bin/env python
"""
E2E Test Runner

Comprehensive test runner with various execution modes and reporting.
"""

import sys
import argparse
from pathlib import Path
import subprocess
import json
import time
from datetime import datetime
from typing import List, Dict, Any


class E2ETestRunner:
    """Run E2E tests with various configurations."""

    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.reports_dir = self.root_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)

    def run_tests(
        self,
        test_suite: str = "all",
        parallel: bool = False,
        headless: bool = True,
        markers: List[str] = None,
        verbose: bool = True
    ) -> int:
        """
        Run E2E tests with specified configuration.

        Args:
            test_suite: Test suite to run (all, smoke, critical, etc.)
            parallel: Run tests in parallel
            headless: Run browsers in headless mode
            markers: Additional pytest markers
            verbose: Verbose output

        Returns:
            Exit code (0 for success)
        """
        # Build pytest command
        cmd = ["pytest"]

        # Add test directory
        cmd.append(str(self.root_dir))

        # Test suite selection
        suite_markers = {
            "smoke": "-m smoke",
            "critical": "-m critical",
            "security": "-m security",
            "performance": "-m performance",
            "workflow": "-m workflow",
            "rag": "-m rag",
            "library": "-m library",
            "all": "",
            "fast": "-m 'not slow'",
            "regression": "-m regression"
        }

        if test_suite in suite_markers:
            if suite_markers[test_suite]:
                cmd.extend(suite_markers[test_suite].split())

        # Additional markers
        if markers:
            for marker in markers:
                cmd.extend(["-m", marker])

        # Parallel execution
        if parallel:
            cmd.extend(["-n", "auto"])

        # Headless mode
        if not headless:
            cmd.append("--headed")

        # Verbosity
        if verbose:
            cmd.append("-vv")

        # Generate unique report name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_report = self.reports_dir / f"report_{test_suite}_{timestamp}.html"

        # Add reporting options
        cmd.extend([
            f"--html={html_report}",
            "--self-contained-html",
            f"--junitxml={self.reports_dir}/junit_{timestamp}.xml"
        ])

        # Print command
        print(f"🚀 Running E2E Tests: {test_suite}")
        print(f"📝 Command: {' '.join(cmd)}")
        print("-" * 60)

        # Run tests
        start_time = time.time()
        result = subprocess.run(cmd, cwd=self.root_dir.parent)
        duration = time.time() - start_time

        # Print summary
        print("-" * 60)
        print(f"✅ Tests completed in {duration:.2f} seconds")
        print(f"📊 Report generated: {html_report}")

        return result.returncode

    def run_suite_sequence(self, suites: List[str]) -> Dict[str, Any]:
        """Run multiple test suites in sequence."""
        results = {}

        for suite in suites:
            print(f"\n{'='*60}")
            print(f"Running suite: {suite}")
            print(f"{'='*60}\n")

            exit_code = self.run_tests(test_suite=suite)
            results[suite] = {
                "exit_code": exit_code,
                "success": exit_code == 0
            }

            # Stop on critical failure
            if suite == "critical" and exit_code != 0:
                print("❌ Critical tests failed. Stopping execution.")
                break

        return results

    def run_ci_tests(self) -> int:
        """Run tests suitable for CI/CD pipeline."""
        print("🔧 Running CI/CD Test Suite")

        # Run critical tests first
        critical_result = self.run_tests(
            test_suite="critical",
            parallel=True,
            headless=True
        )

        if critical_result != 0:
            print("❌ Critical tests failed")
            return critical_result

        # Run smoke tests
        smoke_result = self.run_tests(
            test_suite="smoke",
            parallel=True,
            headless=True
        )

        if smoke_result != 0:
            print("❌ Smoke tests failed")
            return smoke_result

        # Run fast tests
        fast_result = self.run_tests(
            test_suite="fast",
            parallel=True,
            headless=True
        )

        return fast_result

    def run_nightly_tests(self) -> int:
        """Run comprehensive nightly test suite."""
        print("🌙 Running Nightly Test Suite")

        suites = [
            "critical",
            "smoke",
            "workflow",
            "library",
            "rag",
            "security",
            "performance",
            "regression"
        ]

        results = self.run_suite_sequence(suites)

        # Generate summary report
        self.generate_summary_report(results)

        # Return failure if any suite failed
        return 0 if all(r["success"] for r in results.values()) else 1

    def generate_summary_report(self, results: Dict[str, Any]):
        """Generate a summary report of test results."""
        report_path = self.reports_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_suites": len(results),
            "passed_suites": sum(1 for r in results.values() if r["success"]),
            "failed_suites": sum(1 for r in results.values() if not r["success"]),
            "suite_results": results
        }

        report_path.write_text(json.dumps(summary, indent=2))

        # Print summary
        print("\n" + "="*60)
        print("📊 Test Summary")
        print("="*60)
        print(f"Total Suites: {summary['total_suites']}")
        print(f"✅ Passed: {summary['passed_suites']}")
        print(f"❌ Failed: {summary['failed_suites']}")

        for suite, result in results.items():
            status = "✅" if result["success"] else "❌"
            print(f"  {status} {suite}")

        print(f"\n📄 Summary report: {report_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="E2E Test Runner")

    parser.add_argument(
        "suite",
        nargs="?",
        default="all",
        choices=["all", "smoke", "critical", "security", "performance",
                 "workflow", "rag", "library", "fast", "regression", "ci", "nightly"],
        help="Test suite to run"
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel"
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browsers in headed mode (visible)"
    )

    parser.add_argument(
        "--markers",
        nargs="+",
        help="Additional pytest markers"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )

    args = parser.parse_args()

    # Create runner
    runner = E2ETestRunner()

    # Special suites
    if args.suite == "ci":
        exit_code = runner.run_ci_tests()
    elif args.suite == "nightly":
        exit_code = runner.run_nightly_tests()
    else:
        # Regular suite
        exit_code = runner.run_tests(
            test_suite=args.suite,
            parallel=args.parallel,
            headless=not args.headed,
            markers=args.markers,
            verbose=not args.quiet
        )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()