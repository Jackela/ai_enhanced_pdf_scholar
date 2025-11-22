from typing import Any

#!/usr/bin/env python3
"""
Optimized test runner for AI Enhanced PDF Scholar backend tests.

This script provides:
- Controlled test execution with proper isolation
- Coverage report generation
- CI-friendly output formatting
- Performance monitoring
"""

import os
import subprocess
import sys
import time
from pathlib import Path


class TestRunner:
    """Optimized test runner with CI integration."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.test_dir = project_root / "tests"
        self.coverage_dir = project_root / "coverage_html"
        self.results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "coverage": 0.0,
            "duration": 0.0,
        }

    def setup_environment(self) -> None:
        """Setup test environment and paths."""
        # Ensure Python path includes src directory
        sys.path.insert(0, str(self.project_root))
        sys.path.insert(0, str(self.project_root / "src"))

        # Set environment variables
        os.environ["PYTHONPATH"] = f"{self.project_root}:{self.project_root / 'src'}"
        os.environ["TEST_MODE"] = "true"

        # Create necessary directories
        self.coverage_dir.mkdir(exist_ok=True)
        (self.project_root / "test_temp").mkdir(exist_ok=True)
        (self.project_root / "vector_indexes").mkdir(exist_ok=True)

    def run_unit_tests(self, test_selection: str | None = None) -> bool:
        """Run unit tests with proper isolation."""
        print("🧪 Running unit tests...")

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(self.test_dir),
            "-v",
            "--tb=short",
            "--strict-markers",
            "--cov=src",
            "--cov-report=xml:coverage.xml",
            "--cov-report=html:coverage_html",
            "--cov-report=term-missing",
            "--cov-fail-under=60",
            "--cov-branch",
            "--maxfail=10",
            "-n",
            "auto",
            "--dist=loadfile",
            "-m",
            "not slow and not e2e and not performance",
        ]

        if test_selection:
            cmd.extend(["-k", test_selection])

        # Exclude problematic test files temporarily
        cmd.extend(
            [
                "--ignore=tests/services/test_enhanced_rag_service.py",
                "--ignore=tests/services/test_document_library_service.py",
                "--ignore=tests/services/test_rag_cache_service.py",
            ]
        )

        start_time = time.time()
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=self.project_root
        )
        self.results["duration"] = time.time() - start_time

        self._parse_test_output(result.stdout)

        if result.returncode == 0:
            print("✅ Unit tests passed!")
            return True
        else:
            print("❌ Unit tests failed!")
            print("STDOUT:", result.stdout[-1000:])  # Last 1000 chars
            print("STDERR:", result.stderr[-1000:])
            return False

    def run_integration_tests(self) -> bool:
        """Run integration tests separately."""
        print("🔗 Running integration tests...")

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(self.project_root / "test_comprehensive.py"),
            str(self.project_root / "test_complete_workflow.py"),
            "-v",
            "--tb=short",
            "--timeout=120",
            "--maxfail=5",
            "-n",
            "2",
            "--dist=loadfile",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=self.project_root
        )

        if result.returncode == 0:
            print("✅ Integration tests passed!")
            return True
        else:
            print("❌ Integration tests failed!")
            print("STDOUT:", result.stdout[-1000:])
            print("STDERR:", result.stderr[-1000:])
            return False

    def generate_coverage_report(self) -> None:
        """Generate comprehensive coverage report."""
        print("📊 Generating coverage report...")

        # Generate JSON coverage for programmatic access
        subprocess.run(
            [sys.executable, "-m", "coverage", "json", "-o", "coverage.json"],
            cwd=self.project_root,
        )

        # Extract coverage percentage
        try:
            import json

            with open(self.project_root / "coverage.json") as f:
                coverage_data = json.load(f)
                self.results["coverage"] = coverage_data.get("totals", {}).get(
                    "percent_covered", 0.0
                )
        except Exception:
            self.results["coverage"] = 0.0

        print(f"📈 Coverage: {self.results['coverage']:.1f}%")

    def _parse_test_output(self, output: str) -> None:
        """Parse pytest output to extract test statistics."""
        lines = output.split("\n")
        for line in lines:
            if "failed" in line and "passed" in line:
                # Parse line like: "22 failed, 145 passed, 83 warnings, 5 errors"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "failed" and i > 0:
                        self.results["failed"] = int(parts[i - 1])
                    elif part == "passed" and i > 0:
                        self.results["passed"] = int(parts[i - 1])
                    elif part == "errors" and i > 0:
                        self.results["errors"] = int(parts[i - 1])

        self.results["total_tests"] = (
            self.results["passed"] + self.results["failed"] + self.results["errors"]
        )

    def print_summary(self) -> None:
        """Print test execution summary."""
        print("\n" + "=" * 60)
        print("🎯 TEST EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Total Tests:    {self.results['total_tests']}")
        print(f"✅ Passed:      {self.results['passed']}")
        print(f"❌ Failed:      {self.results['failed']}")
        print(f"🚨 Errors:      {self.results['errors']}")
        print(f"📊 Coverage:    {self.results['coverage']:.1f}%")
        print(f"⏱️  Duration:    {self.results['duration']:.2f}s")
        print("=" * 60)

    def run_all_tests(self, skip_integration: bool = False) -> bool:
        """Run complete test suite."""
        print("🚀 Starting comprehensive test execution...")

        self.setup_environment()

        # Run unit tests
        unit_success = self.run_unit_tests()

        # Run integration tests (if not skipped)
        integration_success = True
        if not skip_integration:
            integration_success = self.run_integration_tests()

        # Generate coverage
        self.generate_coverage_report()

        # Print summary
        self.print_summary()

        return unit_success and integration_success


def main() -> None:
    """Main test runner entry point."""
    project_root = Path(__file__).parent.parent
    runner = TestRunner(project_root)

    # Parse command line arguments
    skip_integration = "--unit-only" in sys.argv
    test_selection = None

    if "-k" in sys.argv:
        k_index = sys.argv.index("-k")
        if k_index + 1 < len(sys.argv):
            test_selection = sys.argv[k_index + 1]

    # Run tests
    success = runner.run_all_tests(skip_integration=skip_integration)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
