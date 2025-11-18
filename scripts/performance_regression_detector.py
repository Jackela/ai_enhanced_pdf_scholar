#!/usr/bin/env python3
"""
Performance Regression Detection Script
Compares current performance metrics against established baselines to detect regressions.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PerformanceRegression:
    """Represents a detected performance regression"""

    def __init__(
        self,
        metric_name: str,
        baseline: float,
        current: float,
        change_percent: float,
        severity: str,
    ) -> None:
        self.metric_name = metric_name
        self.baseline = baseline
        self.current = current
        self.change_percent = change_percent
        self.severity = severity  # "minor", "major", "critical"

    def __str__(self) -> Any:
        symbol = (
            "🔴"
            if self.severity == "critical"
            else "🟡"
            if self.severity == "major"
            else "🟠"
        )
        return f"{symbol} {self.metric_name}: {self.baseline:.2f}ms → {self.current:.2f}ms ({self.change_percent:+.1f}%)"


class PerformanceBaseline:
    """Manages performance baselines and regression detection"""

    def __init__(self, baseline_file: Path = None) -> None:
        self.baseline_file = baseline_file or Path("performance_baselines.json")
        self.baselines = self.load_baselines()

    def load_baselines(self) -> dict[str, Any]:
        """Load performance baselines from file"""
        if not self.baseline_file.exists():
            logger.info("No baseline file found, will create one")
            return {}

        try:
            with open(self.baseline_file) as f:
                baselines = json.load(f)
            logger.info(f"Loaded baselines from {self.baseline_file}")
            return baselines
        except Exception as e:
            logger.error(f"Failed to load baselines: {e}")
            return {}

    def save_baselines(self) -> None:
        """Save baselines to file"""
        try:
            with open(self.baseline_file, "w") as f:
                json.dump(self.baselines, f, indent=2, default=str)
            logger.info(f"Saved baselines to {self.baseline_file}")
        except Exception as e:
            logger.error(f"Failed to save baselines: {e}")

    def establish_baselines(
        self, benchmark_results: dict[str, Any], category: str = "default"
    ) -> None:
        """Establish new performance baselines from benchmark results"""
        logger.info(f"Establishing baselines for category: {category}")

        if category not in self.baselines:
            self.baselines[category] = {
                "created_at": datetime.now().isoformat(),
                "metrics": {},
            }

        self.baselines[category]["updated_at"] = datetime.now().isoformat()

        # Extract metrics from different result formats
        metrics = self._extract_metrics_from_results(benchmark_results)

        for metric_name, value in metrics.items():
            self.baselines[category]["metrics"][metric_name] = {
                "value": value,
                "timestamp": datetime.now().isoformat(),
                "type": (
                    "response_time_ms" if "ms" in metric_name.lower() else "throughput"
                ),
            }

        logger.info(f"Established {len(metrics)} baseline metrics")
        self.save_baselines()

    def _extract_metrics_from_results(
        self, results: dict[str, Any]
    ) -> dict[str, float]:
        """Extract numeric metrics from various result formats"""
        metrics = {}

        # Handle simple benchmark format
        if "database_queries" in results:
            for query in results["database_queries"]:
                metric_name = f"db_query_{query['operation']}_avg_ms"
                metrics[metric_name] = query["avg_ms"]

        if "file_operations" in results:
            for file_op in results["file_operations"]:
                metric_name = f"file_op_{file_op['operation']}_avg_ms"
                metrics[metric_name] = file_op["avg_ms"]

                metric_name = f"file_op_{file_op['operation']}_throughput_mb_s"
                metrics[metric_name] = file_op.get("throughput_mb_per_sec", 0)

        if "text_processing" in results:
            for text_proc in results["text_processing"]:
                metric_name = f"text_proc_{text_proc['operation']}_avg_ms"
                metrics[metric_name] = text_proc["avg_ms"]

        # Handle API benchmark format
        for category in [
            "system_endpoints",
            "document_endpoints",
            "rag_endpoints",
            "settings_endpoints",
        ]:
            if category in results:
                for endpoint, result in results[category].items():
                    if "error" not in result and "response_times_ms" in result:
                        rt = result["response_times_ms"]
                        metric_name = f"api_{endpoint}_mean_ms"
                        metrics[metric_name] = rt["mean"]

                        metric_name = f"api_{endpoint}_p95_ms"
                        metrics[metric_name] = rt["p95"]

                        metric_name = f"api_{endpoint}_success_rate"
                        metrics[metric_name] = result.get("success_rate_percent", 0)

        return metrics

    def detect_regressions(
        self,
        current_results: dict[str, Any],
        category: str = "default",
        regression_threshold: float = 20.0,
    ) -> list[PerformanceRegression]:
        """Detect performance regressions compared to baselines"""

        if category not in self.baselines:
            logger.warning(f"No baselines found for category {category}")
            return []

        baseline_metrics = self.baselines[category]["metrics"]
        current_metrics = self._extract_metrics_from_results(current_results)

        regressions = []

        for metric_name, current_value in current_metrics.items():
            if metric_name not in baseline_metrics:
                logger.info(f"New metric detected: {metric_name}")
                continue

            baseline_value = baseline_metrics[metric_name]["value"]

            if baseline_value == 0:
                continue  # Skip division by zero

            change_percent = ((current_value - baseline_value) / baseline_value) * 100

            # Determine if this is a regression (performance got worse)
            is_regression = False
            if "success_rate" in metric_name:
                # For success rates, lower is worse
                is_regression = (
                    change_percent < -regression_threshold / 2
                )  # More sensitive for success rates
            else:
                # For response times, higher is worse
                is_regression = change_percent > regression_threshold

            if is_regression:
                # Determine severity
                if abs(change_percent) > regression_threshold * 3:
                    severity = "critical"
                elif abs(change_percent) > regression_threshold * 1.5:
                    severity = "major"
                else:
                    severity = "minor"

                regression = PerformanceRegression(
                    metric_name=metric_name,
                    baseline=baseline_value,
                    current=current_value,
                    change_percent=change_percent,
                    severity=severity,
                )
                regressions.append(regression)

        return regressions

    def check_improvements(
        self,
        current_results: dict[str, Any],
        category: str = "default",
        improvement_threshold: float = 15.0,
    ) -> list[dict[str, Any]]:
        """Detect performance improvements"""

        if category not in self.baselines:
            return []

        baseline_metrics = self.baselines[category]["metrics"]
        current_metrics = self._extract_metrics_from_results(current_results)

        improvements = []

        for metric_name, current_value in current_metrics.items():
            if metric_name not in baseline_metrics:
                continue

            baseline_value = baseline_metrics[metric_name]["value"]

            if baseline_value == 0:
                continue

            change_percent = ((current_value - baseline_value) / baseline_value) * 100

            # Determine if this is an improvement
            is_improvement = False
            if "success_rate" in metric_name:
                # For success rates, higher is better
                is_improvement = change_percent > improvement_threshold / 2
            else:
                # For response times, lower is better
                is_improvement = change_percent < -improvement_threshold

            if is_improvement:
                improvements.append(
                    {
                        "metric_name": metric_name,
                        "baseline": baseline_value,
                        "current": current_value,
                        "change_percent": change_percent,
                    }
                )

        return improvements

    def generate_report(
        self, current_results: dict[str, Any], category: str = "default"
    ) -> dict[str, Any]:
        """Generate comprehensive performance comparison report"""

        regressions = self.detect_regressions(current_results, category)
        improvements = self.check_improvements(current_results, category)

        report = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "baseline_info": self.baselines.get(category, {}).get(
                "created_at", "Unknown"
            ),
            "regressions": {
                "count": len(regressions),
                "critical": len([r for r in regressions if r.severity == "critical"]),
                "major": len([r for r in regressions if r.severity == "major"]),
                "minor": len([r for r in regressions if r.severity == "minor"]),
                "details": [
                    {
                        "metric": r.metric_name,
                        "baseline": r.baseline,
                        "current": r.current,
                        "change_percent": r.change_percent,
                        "severity": r.severity,
                    }
                    for r in regressions
                ],
            },
            "improvements": {"count": len(improvements), "details": improvements},
            "overall_status": self._determine_overall_status(regressions),
            "recommendations": self._generate_recommendations(
                regressions, improvements
            ),
        }

        return report

    def _determine_overall_status(
        self, regressions: list[PerformanceRegression]
    ) -> str:
        """Determine overall performance status"""
        if not regressions:
            return "✅ GOOD - No performance regressions detected"

        critical_count = len([r for r in regressions if r.severity == "critical"])
        major_count = len([r for r in regressions if r.severity == "major"])

        if critical_count > 0:
            return f"🔴 CRITICAL - {critical_count} critical regression(s) detected"
        elif major_count > 0:
            return f"🟡 WARNING - {major_count} major regression(s) detected"
        else:
            return f"🟠 CAUTION - {len(regressions)} minor regression(s) detected"

    def _generate_recommendations(
        self, regressions: list[PerformanceRegression], improvements: list[dict]
    ) -> list[str]:
        """Generate recommendations based on analysis"""
        recommendations = []

        if not regressions and not improvements:
            recommendations.append("Performance is stable. Continue monitoring.")
            return recommendations

        if regressions:
            critical_regressions = [r for r in regressions if r.severity == "critical"]
            if critical_regressions:
                recommendations.append(
                    "🔴 URGENT: Investigate critical performance regressions immediately"
                )
                recommendations.append(
                    "Consider rolling back recent changes if possible"
                )

            db_regressions = [r for r in regressions if "db_" in r.metric_name]
            if db_regressions:
                recommendations.append(
                    "🗄️ Database performance issues detected - check indexes and queries"
                )

            api_regressions = [r for r in regressions if "api_" in r.metric_name]
            if api_regressions:
                recommendations.append(
                    "🌐 API performance regressions detected - review endpoint optimizations"
                )

            file_regressions = [r for r in regressions if "file_" in r.metric_name]
            if file_regressions:
                recommendations.append(
                    "📁 File I/O performance issues - check disk usage and file operations"
                )

        if improvements:
            recommendations.append(
                f"✅ {len(improvements)} performance improvements detected - good job!"
            )

        recommendations.append(
            "📊 Update performance baselines if changes are intentional"
        )
        recommendations.append("🔄 Run benchmarks regularly to catch regressions early")

        return recommendations

    def print_report(self, report: dict[str, Any]) -> None:
        """Print formatted performance report"""
        print("\n" + "=" * 80)
        print("PERFORMANCE REGRESSION ANALYSIS REPORT")
        print("=" * 80)

        print(f"📅 Analysis Time: {report['timestamp']}")
        print(f"📊 Category: {report['category']}")
        print(f"📍 Baseline From: {report['baseline_info']}")

        # Overall status
        print(f"\n🎯 Overall Status: {report['overall_status']}")

        # Regressions
        regressions = report["regressions"]
        if regressions["count"] > 0:
            print(f"\n🚨 REGRESSIONS DETECTED ({regressions['count']}):")
            print(f"   🔴 Critical: {regressions['critical']}")
            print(f"   🟡 Major: {regressions['major']}")
            print(f"   🟠 Minor: {regressions['minor']}")

            print("\n📋 Regression Details:")
            for reg in regressions["details"][:10]:  # Show first 10
                severity_symbol = (
                    "🔴"
                    if reg["severity"] == "critical"
                    else "🟡"
                    if reg["severity"] == "major"
                    else "🟠"
                )
                print(f"   {severity_symbol} {reg['metric']}:")
                print(
                    f"      Baseline: {reg['baseline']:.2f} → Current: {reg['current']:.2f}"
                )
                print(f"      Change: {reg['change_percent']:+.1f}%")
        else:
            print("\n✅ No performance regressions detected")

        # Improvements
        improvements = report["improvements"]
        if improvements["count"] > 0:
            print(f"\n🚀 IMPROVEMENTS DETECTED ({improvements['count']}):")
            for imp in improvements["details"][:5]:  # Show first 5
                print(
                    f"   ✅ {imp['metric_name']}: {imp['change_percent']:+.1f}% improvement"
                )

        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"   {i}. {rec}")

        print("\n" + "=" * 80)


def main() -> Any:
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Performance Regression Detector")
    parser.add_argument(
        "--results", required=True, help="Path to current benchmark results JSON file"
    )
    parser.add_argument(
        "--baseline", help="Path to baseline file (default: performance_baselines.json)"
    )
    parser.add_argument(
        "--category", default="default", help="Baseline category to compare against"
    )
    parser.add_argument(
        "--establish",
        action="store_true",
        help="Establish new baselines instead of detecting regressions",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=20.0,
        help="Regression threshold percentage (default: 20%)",
    )
    parser.add_argument("--output", help="Save report to JSON file")

    args = parser.parse_args()

    # Load current results
    try:
        with open(args.results) as f:
            current_results = json.load(f)
        logger.info(f"Loaded benchmark results from {args.results}")
    except Exception as e:
        logger.error(f"Failed to load results file: {e}")
        return 1

    # Initialize baseline manager
    baseline_file = Path(args.baseline) if args.baseline else None
    detector = PerformanceBaseline(baseline_file)

    try:
        if args.establish:
            # Establish new baselines
            detector.establish_baselines(current_results, args.category)
            print(
                f"✅ Established new performance baselines for category '{args.category}'"
            )
            return 0
        else:
            # Detect regressions
            report = detector.generate_report(current_results, args.category)
            detector.print_report(report)

            # Save report if requested
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(report, f, indent=2, default=str)
                logger.info(f"Report saved to {args.output}")

            # Exit with appropriate code
            if report["regressions"]["critical"] > 0:
                return 2  # Critical regressions
            elif report["regressions"]["major"] > 0:
                return 1  # Major regressions
            else:
                return 0  # No significant regressions

    except Exception as e:
        logger.error(f"Regression detection failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
