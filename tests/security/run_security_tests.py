#!/usr/bin/env python
"""
Security Test Suite Runner
Comprehensive security testing with reporting and CI/CD integration.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest


class SecurityTestRunner:
    """Run and manage security tests."""

    def __init__(self, config: dict[str, Any] = None):
        self.config = config or self.get_default_config()
        self.results = []
        self.report_dir = Path("tests/security/reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_default_config() -> dict[str, Any]:
        """Get default test configuration."""
        return {
            "parallel": True,
            "workers": 4,
            "timeout": 300,
            "markers": [],
            "verbose": True,
            "coverage": True,
            "report_format": "json",
            "fail_on_critical": True,
            "baseline_comparison": True
        }

    def run_all_tests(self) -> dict[str, Any]:
        """Run all security tests."""
        print("=" * 80)
        print("SECURITY TEST SUITE - COMPREHENSIVE SCAN")
        print("=" * 80)

        start_time = time.time()

        # Test categories
        test_suites = [
            ("Critical Security", "-m critical", True),
            ("Input Validation", "test_input_validation_comprehensive.py", False),
            ("XSS Protection", "test_xss_protection.py", False),
            ("Rate Limiting & DDoS", "test_rate_limiting_ddos.py", False),
            ("SQL Injection", "test_sql_injection_prevention.py", False),
            ("Authentication", "test_authentication_authorization.py", False),
            ("File Upload", "test_file_upload_security.py", False),
            ("CORS Security", "test_cors_security.py", False),
            ("Security Regression", "test_security_regression.py", True),
        ]

        overall_results = {
            "timestamp": datetime.now().isoformat(),
            "duration": 0,
            "suites": {},
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "errors": 0,
                "vulnerabilities": []
            }
        }

        for suite_name, test_spec, is_critical in test_suites:
            print(f"\n[*] Running {suite_name} tests...")
            print("-" * 60)

            result = self.run_test_suite(test_spec, suite_name)
            overall_results["suites"][suite_name] = result

            # Update summary
            overall_results["summary"]["total_tests"] += result["total"]
            overall_results["summary"]["passed"] += result["passed"]
            overall_results["summary"]["failed"] += result["failed"]
            overall_results["summary"]["skipped"] += result.get("skipped", 0)
            overall_results["summary"]["errors"] += result.get("errors", 0)

            # Check for critical failures
            if is_critical and result["failed"] > 0 and self.config["fail_on_critical"]:
                print(f"\n[!] CRITICAL: {suite_name} tests failed!")
                overall_results["summary"]["vulnerabilities"].append({
                    "type": "critical",
                    "suite": suite_name,
                    "failures": result["failed"]
                })

        overall_results["duration"] = time.time() - start_time

        # Generate reports
        self.generate_report(overall_results)
        self.print_summary(overall_results)

        # Check baseline
        if self.config["baseline_comparison"]:
            self.compare_with_baseline(overall_results)

        return overall_results

    def run_test_suite(self, test_spec: str, suite_name: str) -> dict[str, Any]:
        """Run a specific test suite."""
        pytest_args = [
            "tests/security",
            "-v" if self.config["verbose"] else "-q",
            "--tb=short",
            "--json-report",
            f"--json-report-file={self.report_dir}/temp_{suite_name.replace(' ', '_')}.json"
        ]

        # Add test specification
        if test_spec.startswith("-m"):
            pytest_args.extend(test_spec.split())
        else:
            pytest_args.append(test_spec)

        # Add parallelization
        if self.config["parallel"]:
            pytest_args.extend(["-n", str(self.config["workers"])])

        # Add coverage if enabled
        if self.config["coverage"]:
            pytest_args.extend([
                "--cov=backend",
                "--cov-report=term-missing",
                f"--cov-report=html:{self.report_dir}/coverage_{suite_name.replace(' ', '_')}"
            ])

        # Run tests
        result = pytest.main(pytest_args)

        # Parse results
        report_file = self.report_dir / f"temp_{suite_name.replace(' ', '_')}.json"
        if report_file.exists():
            with open(report_file) as f:
                report_data = json.load(f)

                return {
                    "total": report_data["summary"]["total"],
                    "passed": report_data["summary"]["passed"],
                    "failed": report_data["summary"]["failed"],
                    "skipped": report_data["summary"].get("skipped", 0),
                    "errors": report_data["summary"].get("errors", 0),
                    "duration": report_data["duration"],
                    "exit_code": result
                }

        # Fallback if report parsing fails
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 0,
            "exit_code": result
        }

    def run_quick_scan(self) -> dict[str, Any]:
        """Run quick security scan (critical tests only)."""
        print("=" * 80)
        print("QUICK SECURITY SCAN - CRITICAL TESTS ONLY")
        print("=" * 80)

        return self.run_test_suite("-m critical", "Quick Scan")

    def run_specific_tests(self, test_types: list[str]) -> dict[str, Any]:
        """Run specific types of security tests."""
        results = {}

        test_mapping = {
            "sql": "test_sql_injection_prevention.py",
            "xss": "test_xss_protection.py",
            "auth": "test_authentication_authorization.py",
            "rate": "test_rate_limiting_ddos.py",
            "input": "test_input_validation_comprehensive.py",
            "file": "test_file_upload_security.py",
            "cors": "test_cors_security.py",
            "regression": "test_security_regression.py"
        }

        for test_type in test_types:
            if test_type in test_mapping:
                print(f"\n[*] Running {test_type} tests...")
                results[test_type] = self.run_test_suite(
                    test_mapping[test_type],
                    test_type.upper()
                )

        return results

    def generate_report(self, results: dict[str, Any]):
        """Generate test report in various formats."""
        timestamp = int(time.time())

        # JSON report
        json_report = self.report_dir / f"security_report_{timestamp}.json"
        with open(json_report, 'w') as f:
            json.dump(results, f, indent=2)

        # HTML report
        html_report = self.report_dir / f"security_report_{timestamp}.html"
        self.generate_html_report(results, html_report)

        # Markdown report for CI/CD
        md_report = self.report_dir / f"security_report_{timestamp}.md"
        self.generate_markdown_report(results, md_report)

        print("\n[+] Reports generated:")
        print(f"    - JSON: {json_report}")
        print(f"    - HTML: {html_report}")
        print(f"    - Markdown: {md_report}")

    def generate_html_report(self, results: dict[str, Any], output_file: Path):
        """Generate HTML report."""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Security Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .skipped {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        .vulnerability {{ background-color: #ffcccc; }}
    </style>
</head>
<body>
    <h1>Security Test Report</h1>
    <p>Generated: {results['timestamp']}</p>
    <p>Duration: {results['duration']:.2f} seconds</p>

    <div class="summary">
        <h2>Summary</h2>
        <p>Total Tests: {results['summary']['total_tests']}</p>
        <p class="passed">Passed: {results['summary']['passed']}</p>
        <p class="failed">Failed: {results['summary']['failed']}</p>
        <p class="skipped">Skipped: {results['summary']['skipped']}</p>
        <p>Errors: {results['summary']['errors']}</p>
    </div>

    <h2>Test Suites</h2>
    <table>
        <tr>
            <th>Suite</th>
            <th>Total</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Duration</th>
        </tr>
"""

        for suite_name, suite_result in results["suites"].items():
            row_class = "vulnerability" if suite_result["failed"] > 0 else ""
            html_content += f"""
        <tr class="{row_class}">
            <td>{suite_name}</td>
            <td>{suite_result['total']}</td>
            <td>{suite_result['passed']}</td>
            <td>{suite_result['failed']}</td>
            <td>{suite_result['duration']:.2f}s</td>
        </tr>
"""

        html_content += """
    </table>

    <h2>Vulnerabilities</h2>
"""

        if results["summary"]["vulnerabilities"]:
            html_content += "<ul>"
            for vuln in results["summary"]["vulnerabilities"]:
                html_content += f"<li class='failed'>{vuln['type']}: {vuln['suite']} ({vuln['failures']} failures)</li>"
            html_content += "</ul>"
        else:
            html_content += "<p class='passed'>No critical vulnerabilities detected!</p>"

        html_content += """
</body>
</html>
"""

        with open(output_file, 'w') as f:
            f.write(html_content)

    def generate_markdown_report(self, results: dict[str, Any], output_file: Path):
        """Generate Markdown report for CI/CD."""
        md_content = f"""# Security Test Report

**Generated:** {results['timestamp']}
**Duration:** {results['duration']:.2f} seconds

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | {results['summary']['total_tests']} |
| Passed | ✅ {results['summary']['passed']} |
| Failed | ❌ {results['summary']['failed']} |
| Skipped | ⚠️ {results['summary']['skipped']} |
| Errors | 🚫 {results['summary']['errors']} |

## Test Suites

| Suite | Total | Passed | Failed | Duration |
|-------|-------|--------|--------|----------|
"""

        for suite_name, suite_result in results["suites"].items():
            status = "✅" if suite_result["failed"] == 0 else "❌"
            md_content += f"| {status} {suite_name} | {suite_result['total']} | {suite_result['passed']} | {suite_result['failed']} | {suite_result['duration']:.2f}s |\n"

        md_content += "\n## Vulnerabilities\n\n"

        if results["summary"]["vulnerabilities"]:
            for vuln in results["summary"]["vulnerabilities"]:
                md_content += f"- **{vuln['type']}**: {vuln['suite']} ({vuln['failures']} failures)\n"
        else:
            md_content += "✅ **No critical vulnerabilities detected!**\n"

        with open(output_file, 'w') as f:
            f.write(md_content)

    def compare_with_baseline(self, results: dict[str, Any]):
        """Compare results with security baseline."""
        baseline_file = Path("tests/security/security_baseline.json")

        if not baseline_file.exists():
            print("\n[!] No baseline found. Creating new baseline...")
            self.create_baseline(results)
            return

        with open(baseline_file) as f:
            baseline = json.load(f)

        print("\n[*] Comparing with baseline...")

        # Compare test counts
        if results["summary"]["failed"] > baseline.get("max_failures", 0):
            print(f"[!] REGRESSION: More failures than baseline "
                  f"({results['summary']['failed']} > {baseline.get('max_failures', 0)})")

        # Check for new vulnerabilities
        current_vulns = {v["suite"] for v in results["summary"]["vulnerabilities"]}
        baseline_vulns = set(baseline.get("known_vulnerabilities", []))

        new_vulns = current_vulns - baseline_vulns
        if new_vulns:
            print(f"[!] NEW VULNERABILITIES: {new_vulns}")

        fixed_vulns = baseline_vulns - current_vulns
        if fixed_vulns:
            print(f"[+] FIXED VULNERABILITIES: {fixed_vulns}")

    def create_baseline(self, results: dict[str, Any]):
        """Create security baseline from current results."""
        baseline = {
            "version": "1.0.0",
            "created": datetime.now().isoformat(),
            "max_failures": results["summary"]["failed"],
            "known_vulnerabilities": [v["suite"] for v in results["summary"]["vulnerabilities"]],
            "test_counts": {
                "total": results["summary"]["total_tests"],
                "passed": results["summary"]["passed"]
            }
        }

        baseline_file = Path("tests/security/security_baseline.json")
        with open(baseline_file, 'w') as f:
            json.dump(baseline, f, indent=2)

        print(f"[+] Baseline created: {baseline_file}")

    def print_summary(self, results: dict[str, Any]):
        """Print test summary to console."""
        print("\n" + "=" * 80)
        print("SECURITY TEST SUMMARY")
        print("=" * 80)

        total = results["summary"]["total_tests"]
        passed = results["summary"]["passed"]
        failed = results["summary"]["failed"]

        pass_rate = (passed / total * 100) if total > 0 else 0

        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ({pass_rate:.1f}%)")
        print(f"Failed: {failed}")
        print(f"Skipped: {results['summary']['skipped']}")
        print(f"Errors: {results['summary']['errors']}")
        print(f"\nDuration: {results['duration']:.2f} seconds")

        if results["summary"]["vulnerabilities"]:
            print("\n⚠️  VULNERABILITIES DETECTED:")
            for vuln in results["summary"]["vulnerabilities"]:
                print(f"  - {vuln['type']}: {vuln['suite']}")
        else:
            print("\n✅ No critical vulnerabilities detected!")

        # Exit code based on results
        if failed > 0 or results["summary"]["errors"] > 0:
            print("\n❌ SECURITY TESTS FAILED")
            return 1
        else:
            print("\n✅ SECURITY TESTS PASSED")
            return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Security Test Suite Runner")

    parser.add_argument(
        "--mode",
        choices=["full", "quick", "specific"],
        default="full",
        help="Test mode to run"
    )

    parser.add_argument(
        "--tests",
        nargs="+",
        help="Specific test types to run (sql, xss, auth, etc.)"
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="Run tests in parallel"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers"
    )

    parser.add_argument(
        "--coverage",
        action="store_true",
        default=True,
        help="Generate coverage report"
    )

    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip baseline comparison"
    )

    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI/CD mode with strict checks"
    )

    args = parser.parse_args()

    # Configure runner
    config = {
        "parallel": args.parallel,
        "workers": args.workers,
        "coverage": args.coverage,
        "baseline_comparison": not args.no_baseline,
        "fail_on_critical": args.ci,
        "verbose": not args.ci
    }

    runner = SecurityTestRunner(config)

    # Run tests based on mode
    if args.mode == "full":
        results = runner.run_all_tests()
    elif args.mode == "quick":
        results = runner.run_quick_scan()
    elif args.mode == "specific" and args.tests:
        results = runner.run_specific_tests(args.tests)
    else:
        print("Invalid mode or missing test specification")
        sys.exit(1)

    # Exit with appropriate code
    exit_code = 1 if results["summary"]["failed"] > 0 else 0
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
