#!/usr/bin/env python3
"""
Test Infrastructure Optimization Script
Analyzes and optimizes test performance and infrastructure.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


class TestOptimizer:
    """Test infrastructure optimizer and analyzer."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = Path(project_root)
        self.test_dir = self.project_root / "tests"
        self.results: dict[str, Any] = {}

    def analyze_test_structure(self) -> dict[str, Any]:
        """Analyze current test structure and complexity."""
        print("🔍 Analyzing test structure...")

        # Count test files
        test_files = list(self.test_dir.rglob("test_*.py"))
        conftest_files = list(self.test_dir.rglob("conftest.py"))

        # Analyze conftest complexity
        conftest_analysis = []
        for conftest in conftest_files:
            try:
                content = conftest.read_text()
                lines = len(content.splitlines())
                fixture_count = content.count("@pytest.fixture")

                conftest_analysis.append(
                    {
                        "file": str(conftest.relative_to(self.project_root)),
                        "lines": lines,
                        "fixtures": fixture_count,
                        "complexity": (
                            "high"
                            if lines > 200
                            else "medium"
                            if lines > 100
                            else "low"
                        ),
                    }
                )
            except Exception as e:
                print(f"Warning: Could not analyze {conftest}: {e}")

        structure = {
            "total_test_files": len(test_files),
            "total_conftest_files": len(conftest_files),
            "conftest_analysis": conftest_analysis,
            "test_categories": self._categorize_tests(test_files),
        }

        self.results["structure"] = structure
        return structure

    def _categorize_tests(self, test_files: list[Path]) -> dict[str, int]:
        """Categorize tests by type."""
        categories = {
            "unit": 0,
            "integration": 0,
            "e2e": 0,
            "security": 0,
            "performance": 0,
            "repository": 0,
            "service": 0,
            "other": 0,
        }

        for test_file in test_files:
            path_str = str(test_file).lower()

            if "unit" in path_str:
                categories["unit"] += 1
            elif "integration" in path_str:
                categories["integration"] += 1
            elif "e2e" in path_str:
                categories["e2e"] += 1
            elif "security" in path_str:
                categories["security"] += 1
            elif "performance" in path_str:
                categories["performance"] += 1
            elif "repository" in path_str or "repositories" in path_str:
                categories["repository"] += 1
            elif "service" in path_str or "services" in path_str:
                categories["service"] += 1
            else:
                categories["other"] += 1

        return categories

    def benchmark_test_performance(self, subset: str = "smoke") -> dict[str, Any]:
        """Benchmark test execution performance."""
        print(f"⚡ Benchmarking test performance ({subset})...")

        # Define test subsets for benchmarking
        test_subsets = {
            "smoke": ["tests/unit/test_smoke.py"],
            "unit": ["-m", "unit"],
            "database": ["-m", "database", "--maxfail=3"],
            "integration": ["-m", "integration", "--maxfail=2"],
            "all": [],
        }

        test_args = test_subsets.get(subset, test_subsets["smoke"])

        # Run benchmark
        start_time = time.time()

        try:
            cmd = [
                "python",
                "-m",
                "pytest",
                "--tb=no",
                "-v",
                "--disable-warnings",
            ] + test_args
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            execution_time = time.time() - start_time

            # Parse output for test results
            output_lines = result.stdout.split("\n")
            test_results = self._parse_pytest_output(output_lines)

            benchmark = {
                "subset": subset,
                "execution_time": round(execution_time, 2),
                "return_code": result.returncode,
                "total_tests": test_results.get("total", 0),
                "passed": test_results.get("passed", 0),
                "failed": test_results.get("failed", 0),
                "skipped": test_results.get("skipped", 0),
                "tests_per_second": round(
                    test_results.get("total", 0) / max(execution_time, 0.1), 2
                ),
                "stderr": result.stderr[:500] if result.stderr else None,
            }

        except subprocess.TimeoutExpired:
            benchmark = {
                "subset": subset,
                "execution_time": 300,
                "return_code": -1,
                "error": "Timeout after 5 minutes",
                "tests_per_second": 0,
            }
        except Exception as e:
            benchmark = {
                "subset": subset,
                "error": str(e),
                "execution_time": time.time() - start_time,
                "tests_per_second": 0,
            }

        self.results["benchmark"] = benchmark
        return benchmark

    def _parse_pytest_output(self, output_lines: list[str]) -> dict[str, int]:
        """Parse pytest output to extract test counts."""
        results = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}

        for line in output_lines:
            line = line.strip()
            if " passed" in line or " failed" in line or " skipped" in line:
                # Look for summary line like "5 passed in 2.34s"
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.isdigit():
                            count = int(part)
                            if i + 1 < len(parts):
                                status = parts[i + 1]
                                if "passed" in status:
                                    results["passed"] = count
                                elif "failed" in status:
                                    results["failed"] = count
                                elif "skipped" in status:
                                    results["skipped"] = count
                except Exception:
                    continue

        results["total"] = results["passed"] + results["failed"] + results["skipped"]
        return results

    def analyze_dependencies(self) -> dict[str, Any]:
        """Analyze test dependencies and imports."""
        print("📦 Analyzing test dependencies...")

        dependencies: Any = {
            "common_imports": {},
            "fixture_dependencies": {},
            "slow_imports": [],
        }

        # Analyze imports in test files
        test_files = list(self.test_dir.rglob("test_*.py"))

        for test_file in test_files[:10]:  # Sample first 10 files
            try:
                content = test_file.read_text()

                # Count imports
                import_lines = [
                    line.strip()
                    for line in content.split("\n")
                    if line.strip().startswith(("import ", "from "))
                ]

                for imp in import_lines:
                    if imp in dependencies["common_imports"]:
                        dependencies["common_imports"][imp] += 1
                    else:
                        dependencies["common_imports"][imp] = 1

                # Check for potentially slow imports
                slow_patterns = [
                    "llama",
                    "torch",
                    "transformers",
                    "tensorflow",
                    "requests",
                ]
                for pattern in slow_patterns:
                    if pattern in content.lower():
                        dependencies["slow_imports"].append(
                            {
                                "file": str(test_file.relative_to(self.project_root)),
                                "pattern": pattern,
                            }
                        )

            except Exception as e:
                print(f"Warning: Could not analyze imports in {test_file}: {e}")

        # Get top 10 most common imports
        dependencies["common_imports"] = dict(
            sorted(
                dependencies["common_imports"].items(), key=lambda x: x[1], reverse=True
            )[:10]
        )

        self.results["dependencies"] = dependencies
        return dependencies

    def generate_optimization_recommendations(self) -> list[dict[str, str]]:
        """Generate actionable optimization recommendations."""
        print("💡 Generating optimization recommendations...")

        recommendations = []

        # Check structure issues
        if "structure" in self.results:
            structure = self.results["structure"]

            # Check conftest complexity
            for conftest in structure.get("conftest_analysis", []):
                if conftest["complexity"] == "high":
                    recommendations.append(
                        {
                            "type": "fixture_optimization",
                            "priority": "high",
                            "title": "Simplify complex conftest.py",
                            "description": f"{conftest['file']} has {conftest['lines']} lines and {conftest['fixtures']} fixtures. Consider splitting or optimizing.",
                            "action": "Split large conftest.py files and optimize fixture scopes",
                        }
                    )

            # Check test organization
            categories = structure.get("test_categories", {})
            if categories.get("other", 0) > categories.get("unit", 0):
                recommendations.append(
                    {
                        "type": "organization",
                        "priority": "medium",
                        "title": "Improve test organization",
                        "description": f"Found {categories['other']} uncategorized tests vs {categories['unit']} unit tests",
                        "action": "Reorganize tests into clear categories (unit, integration, e2e)",
                    }
                )

        # Check performance issues
        if "benchmark" in self.results:
            benchmark = self.results["benchmark"]

            if benchmark.get("tests_per_second", 0) < 2:
                recommendations.append(
                    {
                        "type": "performance",
                        "priority": "high",
                        "title": "Improve test execution speed",
                        "description": f"Tests running at {benchmark.get('tests_per_second', 0):.2f} tests/second",
                        "action": "Optimize fixtures, use mocking, and implement connection pooling",
                    }
                )

        # Check dependency issues
        if "dependencies" in self.results:
            deps = self.results["dependencies"]

            if len(deps.get("slow_imports", [])) > 0:
                recommendations.append(
                    {
                        "type": "dependencies",
                        "priority": "medium",
                        "title": "Optimize slow imports",
                        "description": f"Found {len(deps['slow_imports'])} files with potentially slow imports",
                        "action": "Move slow imports inside test functions or use lazy loading",
                    }
                )

        self.results["recommendations"] = recommendations
        return recommendations

    def generate_report(self) -> str:
        """Generate a comprehensive optimization report."""
        report_lines = [
            "# Test Infrastructure Optimization Report",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
        ]

        # Structure summary
        if "structure" in self.results:
            structure = self.results["structure"]
            report_lines.extend(
                [
                    f"- **Total Test Files**: {structure['total_test_files']}",
                    f"- **Conftest Files**: {structure['total_conftest_files']}",
                    "",
                    "### Test Categories",
                ]
            )

            for category, count in structure.get("test_categories", {}).items():
                report_lines.append(f"- {category.title()}: {count}")

        # Performance summary
        if "benchmark" in self.results:
            benchmark = self.results["benchmark"]
            report_lines.extend(
                [
                    "",
                    "## Performance Benchmark",
                    f"- **Execution Time**: {benchmark.get('execution_time', 0)}s",
                    f"- **Tests/Second**: {benchmark.get('tests_per_second', 0):.2f}",
                    f"- **Success Rate**: {benchmark.get('passed', 0)}/{benchmark.get('total', 0)} tests passed",
                ]
            )

        # Recommendations
        if "recommendations" in self.results:
            report_lines.extend(["", "## Optimization Recommendations", ""])

            for i, rec in enumerate(self.results["recommendations"], 1):
                report_lines.extend(
                    [
                        f"### {i}. {rec['title']} ({rec['priority']} priority)",
                        f"**Type**: {rec['type']}",
                        f"**Description**: {rec['description']}",
                        f"**Action**: {rec['action']}",
                        "",
                    ]
                )

        return "\n".join(report_lines)

    def save_results(self, output_file: str = "test_optimization_results.json") -> None:
        """Save optimization results to file."""
        results_file = self.project_root / output_file

        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"📄 Results saved to {results_file}")

        # Also save markdown report
        report_file = self.project_root / output_file.replace(".json", "_report.md")
        with open(report_file, "w") as f:
            f.write(self.generate_report())

        print(f"📊 Report saved to {report_file}")


def main() -> None:
    """Main optimization script."""
    parser = argparse.ArgumentParser(description="Test Infrastructure Optimizer")
    parser.add_argument(
        "--benchmark",
        choices=["smoke", "unit", "database", "integration", "all"],
        default="smoke",
        help="Test subset to benchmark",
    )
    parser.add_argument(
        "--output",
        default="test_optimization_results.json",
        help="Output file for results",
    )
    parser.add_argument(
        "--skip-benchmark", action="store_true", help="Skip performance benchmarking"
    )

    args = parser.parse_args()

    print("🚀 Starting Test Infrastructure Optimization")
    print("=" * 50)

    optimizer = TestOptimizer()

    # Run analysis
    optimizer.analyze_test_structure()
    optimizer.analyze_dependencies()

    if not args.skip_benchmark:
        optimizer.benchmark_test_performance(args.benchmark)

    optimizer.generate_optimization_recommendations()

    # Generate and display report
    report = optimizer.generate_report()
    print("\n" + report)

    # Save results
    optimizer.save_results(args.output)

    print("\n✅ Optimization analysis complete!")


if __name__ == "__main__":
    main()
