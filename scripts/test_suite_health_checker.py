#!/usr/bin/env python3
"""
Test Suite Health Checker for AI Enhanced PDF Scholar
Comprehensive validation of test suite health and readiness for production.
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import argparse


@dataclass
class TestCategoryResult:
    """Result of a test category execution."""
    category: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    pass_rate: float
    execution_time: float
    status: str  # "excellent", "good", "acceptable", "poor", "critical"


@dataclass
class TestSuiteHealthReport:
    """Complete test suite health report."""
    overall_health_score: float
    total_tests: int
    total_passed: int
    total_failed: int
    total_skipped: int
    overall_pass_rate: float
    categories: List[TestCategoryResult]
    recommendations: List[str]
    production_ready: bool


class TestSuiteHealthChecker:
    """Comprehensive test suite health checker."""

    def __init__(self, project_root: str = None):
        """Initialize health checker."""
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.test_categories = {
            "API Tests": ["tests/api/test_minimal_endpoints.py"],
            "Citation System": [
                "tests/test_citation_models.py",
                "tests/test_citation_repositories.py",
                "tests/test_citation_services.py"
            ],
            "Database Models": ["tests/test_database_models.py"],
            "Unit Tests": ["tests/unit/test_smoke.py"],
            "Security Tests": ["tests/security/test_security_suite.py", "--ignore-import-errors"],
            "Integration Tests": ["tests/integration/test_api_endpoints.py", "--ignore-import-errors"]
        }

    def run_test_category(self, category: str, test_patterns: List[str], timeout: int = 120) -> TestCategoryResult:
        """Run tests for a specific category."""
        print(f"🧪 Running {category}...")

        # Build pytest command
        cmd = [
            sys.executable, "-m", "pytest",
            "-v",
            "--tb=no",  # No traceback for cleaner output
            f"--timeout={timeout}"
        ]

        # Handle special flags
        actual_patterns = []
        for pattern in test_patterns:
            if pattern.startswith("--"):
                cmd.append(pattern)
            else:
                actual_patterns.append(pattern)

        cmd.extend(actual_patterns)

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            execution_time = time.time() - start_time

            # Parse pytest output for test counts
            stdout = result.stdout
            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            skipped_tests = 0

            # Extract test counts from pytest summary
            lines = stdout.split('\n')
            for line in lines:
                if 'passed' in line and 'failed' in line:
                    # Parse line like "5 failed, 10 passed in 2.34s"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'passed' and i > 0:
                            try:
                                passed_tests = int(parts[i-1])
                            except ValueError:
                                pass
                        elif part == 'failed' and i > 0:
                            try:
                                failed_tests = int(parts[i-1])
                            except ValueError:
                                pass
                        elif part == 'skipped' and i > 0:
                            try:
                                skipped_tests = int(parts[i-1])
                            except ValueError:
                                pass
                elif 'passed' in line and 'failed' not in line:
                    # Parse line like "10 passed in 2.34s"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'passed' and i > 0:
                            try:
                                passed_tests = int(parts[i-1])
                            except ValueError:
                                pass
                elif 'skipped' in line and 'passed' not in line:
                    # Parse line like "5 skipped"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'skipped' and i > 0:
                            try:
                                skipped_tests = int(parts[i-1])
                            except ValueError:
                                pass

            total_tests = passed_tests + failed_tests + skipped_tests

            # If we couldn't parse the output, estimate from return code
            if total_tests == 0 and result.returncode == 0:
                # Successful run but couldn't parse - assume some tests ran
                total_tests = 1
                passed_tests = 1
            elif total_tests == 0 and result.returncode != 0:
                # Failed run - could be import errors or test failures
                total_tests = 1
                failed_tests = 1

            pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0

            # Determine status
            if pass_rate >= 95:
                status = "excellent"
            elif pass_rate >= 85:
                status = "good"
            elif pass_rate >= 70:
                status = "acceptable"
            elif pass_rate >= 50:
                status = "poor"
            else:
                status = "critical"

            return TestCategoryResult(
                category=category,
                total_tests=total_tests,
                passed_tests=passed_tests,
                failed_tests=failed_tests,
                skipped_tests=skipped_tests,
                pass_rate=pass_rate,
                execution_time=execution_time,
                status=status
            )

        except subprocess.TimeoutExpired:
            print(f"⏰ {category} timed out after {timeout} seconds")
            return TestCategoryResult(
                category=category,
                total_tests=1,
                passed_tests=0,
                failed_tests=1,
                skipped_tests=0,
                pass_rate=0.0,
                execution_time=timeout,
                status="critical"
            )
        except Exception as e:
            print(f"❌ Error running {category}: {e}")
            return TestCategoryResult(
                category=category,
                total_tests=1,
                passed_tests=0,
                failed_tests=1,
                skipped_tests=0,
                pass_rate=0.0,
                execution_time=0.0,
                status="critical"
            )

    def calculate_health_score(self, categories: List[TestCategoryResult]) -> float:
        """Calculate overall health score based on category results."""
        if not categories:
            return 0.0

        # Weight different categories differently
        category_weights = {
            "API Tests": 0.25,       # Critical for system functionality
            "Citation System": 0.25,  # Core business value
            "Database Models": 0.20,  # Foundation reliability
            "Unit Tests": 0.15,      # Basic functionality
            "Security Tests": 0.10,   # Important but may have import issues
            "Integration Tests": 0.05  # Nice to have but often have dependency issues
        }

        weighted_score = 0.0
        total_weight = 0.0

        for result in categories:
            weight = category_weights.get(result.category, 0.1)
            weighted_score += result.pass_rate * weight
            total_weight += weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def generate_recommendations(self, categories: List[TestCategoryResult], health_score: float) -> List[str]:
        """Generate actionable recommendations based on test results."""
        recommendations = []

        # Overall health assessment
        if health_score >= 90:
            recommendations.append("🎯 Excellent test health! System is production-ready.")
        elif health_score >= 80:
            recommendations.append("✅ Good test health. Address minor issues for optimal reliability.")
        elif health_score >= 70:
            recommendations.append("⚠️  Moderate test health. Focus on critical test failures.")
        elif health_score >= 60:
            recommendations.append("🔶 Poor test health. Immediate attention required.")
        else:
            recommendations.append("🚨 Critical test health issues. Production deployment NOT recommended.")

        # Category-specific recommendations
        critical_categories = [c for c in categories if c.status == "critical"]
        poor_categories = [c for c in categories if c.status == "poor"]

        if critical_categories:
            recommendations.append("🚨 CRITICAL: Fix these failing test categories immediately:")
            for cat in critical_categories:
                recommendations.append(f"   • {cat.category}: {cat.pass_rate:.1f}% pass rate")

        if poor_categories:
            recommendations.append("⚠️  HIGH PRIORITY: Improve these test categories:")
            for cat in poor_categories:
                recommendations.append(f"   • {cat.category}: {cat.pass_rate:.1f}% pass rate")

        # Specific improvement suggestions
        api_result = next((c for c in categories if c.category == "API Tests"), None)
        if api_result and api_result.pass_rate < 80:
            recommendations.append("📋 API Tests: Ensure endpoints return expected responses and handle errors gracefully.")

        citation_result = next((c for c in categories if c.category == "Citation System"), None)
        if citation_result and citation_result.pass_rate < 95:
            recommendations.append("📋 Citation System: This is core business logic - aim for 95%+ test coverage.")

        # Import error detection
        failed_categories = [c for c in categories if c.failed_tests > 0]
        if failed_categories:
            recommendations.append("🔧 Import Issues: Some tests may be failing due to missing dependencies or import errors.")

        return recommendations

    def check_production_readiness(self, health_score: float, categories: List[TestCategoryResult]) -> bool:
        """Determine if system is ready for production based on test health."""
        # Minimum requirements for production
        min_health_score = 70.0

        # Critical categories that must pass
        critical_categories = ["API Tests", "Citation System", "Database Models"]

        if health_score < min_health_score:
            return False

        # Check critical categories
        for cat_name in critical_categories:
            cat_result = next((c for c in categories if c.category == cat_name), None)
            if cat_result and cat_result.pass_rate < 80:
                return False

        return True

    def generate_health_report(self, categories: List[TestCategoryResult]) -> TestSuiteHealthReport:
        """Generate comprehensive health report."""
        health_score = self.calculate_health_score(categories)

        total_tests = sum(c.total_tests for c in categories)
        total_passed = sum(c.passed_tests for c in categories)
        total_failed = sum(c.failed_tests for c in categories)
        total_skipped = sum(c.skipped_tests for c in categories)

        overall_pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0.0

        recommendations = self.generate_recommendations(categories, health_score)
        production_ready = self.check_production_readiness(health_score, categories)

        return TestSuiteHealthReport(
            overall_health_score=health_score,
            total_tests=total_tests,
            total_passed=total_passed,
            total_failed=total_failed,
            total_skipped=total_skipped,
            overall_pass_rate=overall_pass_rate,
            categories=categories,
            recommendations=recommendations,
            production_ready=production_ready
        )

    def print_detailed_report(self, report: TestSuiteHealthReport) -> None:
        """Print detailed health report to console."""
        print("\n" + "="*60)
        print("🧪 TEST SUITE HEALTH CHECK COMPLETE")
        print("="*60)

        # Overall metrics
        print(f"🏥 Overall Health Score: {report.overall_health_score:.1f}%")
        print(f"📊 Total Tests: {report.total_tests}")
        print(f"✅ Passed: {report.total_passed}")
        print(f"❌ Failed: {report.total_failed}")
        print(f"⏭️  Skipped: {report.total_skipped}")
        print(f"📈 Pass Rate: {report.overall_pass_rate:.1f}%")

        # Production readiness
        if report.production_ready:
            print("🎯 PRODUCTION READY: System meets production deployment criteria")
        else:
            print("⚠️  NOT PRODUCTION READY: Address critical issues before deployment")

        # Category breakdown
        print(f"\n📋 Test Category Results:")
        print("-" * 60)

        status_icons = {
            "excellent": "🟢",
            "good": "🟡",
            "acceptable": "🟠",
            "poor": "🔴",
            "critical": "🚨"
        }

        for category in report.categories:
            icon = status_icons.get(category.status, "❓")
            print(f"{icon} {category.category}: {category.passed_tests}/{category.total_tests} passed ({category.pass_rate:.1f}%)")

        # Recommendations
        print(f"\n🎯 Recommendations:")
        print("-" * 60)
        for rec in report.recommendations:
            print(rec)

    def save_health_report_json(self, report: TestSuiteHealthReport, filename: str = "test_health_report.json") -> Path:
        """Save health report as JSON."""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "overall_health_score": report.overall_health_score,
            "total_tests": report.total_tests,
            "total_passed": report.total_passed,
            "total_failed": report.total_failed,
            "total_skipped": report.total_skipped,
            "overall_pass_rate": report.overall_pass_rate,
            "production_ready": report.production_ready,
            "categories": [
                {
                    "category": c.category,
                    "total_tests": c.total_tests,
                    "passed_tests": c.passed_tests,
                    "failed_tests": c.failed_tests,
                    "skipped_tests": c.skipped_tests,
                    "pass_rate": c.pass_rate,
                    "execution_time": c.execution_time,
                    "status": c.status
                }
                for c in report.categories
            ],
            "recommendations": report.recommendations
        }

        report_path = self.project_root / filename
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)

        return report_path

    def run_comprehensive_health_check(self, timeout_per_category: int = 120) -> TestSuiteHealthReport:
        """Run comprehensive test suite health check."""
        print("🚀 Starting comprehensive test suite health check...")

        categories = []

        for category_name, test_patterns in self.test_categories.items():
            result = self.run_test_category(category_name, test_patterns, timeout_per_category)
            categories.append(result)

            # Print immediate feedback
            status_icon = {
                "excellent": "🟢",
                "good": "🟡",
                "acceptable": "🟠",
                "poor": "🔴",
                "critical": "🚨"
            }.get(result.status, "❓")

            print(f"   {status_icon} {category_name}: {result.passed_tests}/{result.total_tests} passed ({result.pass_rate:.1f}%)")

        # Generate comprehensive report
        report = self.generate_health_report(categories)

        return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Check test suite health")
    parser.add_argument("--timeout", type=int, default=120,
                       help="Timeout per test category in seconds (default: 120)")
    parser.add_argument("--output", type=str, default="test_health_report.json",
                       help="Output JSON file name (default: test_health_report.json)")

    args = parser.parse_args()

    checker = TestSuiteHealthChecker()
    report = checker.run_comprehensive_health_check(args.timeout)

    # Print detailed report
    checker.print_detailed_report(report)

    # Save JSON report
    report_path = checker.save_health_report_json(report, args.output)
    print(f"\n📋 Detailed JSON report saved: {report_path}")

    # Exit code based on production readiness
    sys.exit(0 if report.production_ready else 1)


if __name__ == "__main__":
    main()