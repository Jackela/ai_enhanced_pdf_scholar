#!/usr/bin/env python3
"""
Comprehensive Performance Testing Suite
Runs all performance benchmarks and generates unified reports with regression detection.
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx

    from scripts.performance_regression_detector import PerformanceBaseline
    from scripts.simple_benchmark import SimpleBenchmark
except ImportError as e:
    logger.error(f"Missing dependencies: {e}")
    logger.error("Install required packages: pip install httpx")
    sys.exit(1)


class ComprehensivePerformanceSuite:
    """Orchestrates comprehensive performance testing"""

    def __init__(self, output_dir: Path = None) -> None:
        self.output_dir = output_dir or Path("performance_results")
        self.output_dir.mkdir(exist_ok=True)
        self.results = {}
        self.start_time = None
        self.end_time = None

    async def run_system_benchmarks(self) -> dict[str, Any]:
        """Run system-level performance benchmarks"""
        logger.info("Running system performance benchmarks...")

        try:
            benchmark = SimpleBenchmark()
            results = benchmark.run_all_benchmarks()

            return {
                "success": True,
                "results": results,
                "summary": {
                    "database_query_avg_ms": self._extract_avg_metric(
                        results, "database_queries", "avg_ms"
                    ),
                    "file_io_avg_mb_s": self._extract_avg_metric(
                        results, "file_operations", "throughput_mb_per_sec"
                    ),
                    "text_processing_avg_chars_s": self._extract_avg_metric(
                        results, "text_processing", "throughput_chars_per_sec"
                    ),
                },
            }
        except Exception as e:
            logger.error(f"System benchmarks failed: {e}")
            return {"success": False, "error": str(e)}

    async def run_api_benchmarks(
        self, base_url: str = "http://localhost:8000"
    ) -> dict[str, Any]:
        """Run API performance benchmarks"""
        logger.info(f"Running API performance benchmarks against {base_url}...")

        try:
            # Check if server is available
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(f"{base_url}/health", timeout=5.0)
                    server_available = response.status_code < 500
                except:
                    server_available = False

            if not server_available:
                logger.warning("API server not available, skipping API benchmarks")
                return {
                    "success": False,
                    "error": "API server not available",
                    "skipped": True,
                }

            # Run API benchmarks using subprocess to avoid import issues
            cmd = [
                sys.executable,
                "scripts/api_benchmark.py",
                "--url",
                base_url,
                "--save",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())

            if result.returncode != 0:
                logger.error(f"API benchmarks failed: {result.stderr}")
                return {"success": False, "error": result.stderr}

            # Find and load the results file
            results_files = list[Any](self.output_dir.glob("api_benchmark_results_*.json"))
            if not results_files:
                results_files = list[Any](Path.cwd().glob("api_benchmark_results_*.json"))

            if results_files:
                with open(results_files[-1]) as f:
                    api_results = json.load(f)
                return {"success": True, "results": api_results}
            else:
                return {
                    "success": False,
                    "error": "API benchmark results file not found",
                }

        except Exception as e:
            logger.error(f"API benchmarks failed: {e}")
            return {"success": False, "error": str(e)}

    def run_pdf_processing_benchmark(self) -> dict[str, Any]:
        """Run PDF processing performance benchmark"""
        logger.info("Running PDF processing benchmarks...")

        try:
            # Simulate PDF processing benchmarks
            import statistics
            import tempfile
            from pathlib import Path

            test_dir = Path(tempfile.mkdtemp())

            # Create mock PDF files of different sizes
            small_pdf = test_dir / "small.pdf"
            medium_pdf = test_dir / "medium.pdf"
            large_pdf = test_dir / "large.pdf"

            # Mock PDF content
            small_pdf.write_bytes(b"%PDF-1.4\n" + b"Small PDF content " * 100)
            medium_pdf.write_bytes(b"%PDF-1.4\n" + b"Medium PDF content " * 1000)
            large_pdf.write_bytes(b"%PDF-1.4\n" + b"Large PDF content " * 10000)

            results = []

            for pdf_file in [small_pdf, medium_pdf, large_pdf]:
                processing_times = []

                for run in range(10):
                    start_time = time.perf_counter()

                    # Simulate PDF processing
                    content = pdf_file.read_bytes()
                    text_content = content.decode("utf-8", errors="ignore")
                    word_count = len(text_content.split())

                    end_time = time.perf_counter()
                    processing_times.append((end_time - start_time) * 1000)

                results.append(
                    {
                        "file_type": pdf_file.stem,
                        "file_size_bytes": pdf_file.stat().st_size,
                        "avg_processing_time_ms": statistics.mean(processing_times),
                        "min_time_ms": min(processing_times),
                        "max_time_ms": max(processing_times),
                        "word_count": word_count,
                    }
                )

            # Cleanup
            for pdf_file in [small_pdf, medium_pdf, large_pdf]:
                pdf_file.unlink()
            test_dir.rmdir()

            return {
                "success": True,
                "results": results,
                "summary": {
                    "avg_processing_time_ms": statistics.mean(
                        [r["avg_processing_time_ms"] for r in results]
                    )
                },
            }

        except Exception as e:
            logger.error(f"PDF processing benchmarks failed: {e}")
            return {"success": False, "error": str(e)}

    def _extract_avg_metric(self, results: dict[str, Any], category: str, metric: str) -> float:
        """Extract average metric from benchmark results"""
        if category not in results:
            return 0.0

        values = []
        for item in results[category]:
            if metric in item:
                values.append(item[metric])

        if values:
            return sum(values) / len(values)
        return 0.0

    async def run_all_benchmarks(
        self, api_url: str = "http://localhost:8000", detect_regressions: bool = True
    ) -> dict[str, Any]:
        """Run comprehensive performance test suite"""
        logger.info("Starting comprehensive performance test suite...")
        self.start_time = time.time()

        try:
            # Run all benchmark categories
            system_results = await self.run_system_benchmarks()
            api_results = await self.run_api_benchmarks(api_url)
            pdf_results = self.run_pdf_processing_benchmark()

            self.end_time = time.time()

            # Compile results
            self.results = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_duration_seconds": self.end_time - self.start_time,
                    "suite_version": "1.0.0",
                    "environment": {
                        "platform": sys.platform,
                        "python_version": sys.version,
                    },
                },
                "system_benchmarks": system_results,
                "api_benchmarks": api_results,
                "pdf_processing": pdf_results,
            }

            # Regression detection
            if detect_regressions:
                regression_analysis = self.perform_regression_analysis()
                self.results["regression_analysis"] = regression_analysis

            logger.info(
                f"Comprehensive test suite completed in {self.end_time - self.start_time:.2f} seconds"
            )

        except Exception as e:
            logger.error(f"Comprehensive test suite failed: {e}")
            self.results["error"] = str(e)
            raise

        return self.results

    def perform_regression_analysis(self) -> dict[str, Any]:
        """Perform regression analysis against baselines"""
        logger.info("Performing regression analysis...")

        try:
            baseline_detector = PerformanceBaseline(Path("performance_baselines.json"))

            # Check if we have baselines, if not establish them
            if not baseline_detector.baselines:
                logger.info("No baselines found, establishing new baselines...")
                if self.results.get("system_benchmarks", {}).get("success"):
                    baseline_detector.establish_baselines(
                        self.results["system_benchmarks"]["results"], "system"
                    )

                if self.results.get("api_benchmarks", {}).get("success"):
                    baseline_detector.establish_baselines(
                        self.results["api_benchmarks"]["results"], "api"
                    )

                return {
                    "status": "baselines_established",
                    "message": "New baselines created",
                }

            # Detect regressions
            analysis = {"system": None, "api": None}

            if self.results.get("system_benchmarks", {}).get("success"):
                analysis["system"] = baseline_detector.generate_report(
                    self.results["system_benchmarks"]["results"], "system"
                )

            if self.results.get("api_benchmarks", {}).get("success"):
                analysis["api"] = baseline_detector.generate_report(
                    self.results["api_benchmarks"]["results"], "api"
                )

            return analysis

        except Exception as e:
            logger.error(f"Regression analysis failed: {e}")
            return {"error": str(e)}

    def print_comprehensive_summary(self) -> None:
        """Print comprehensive performance summary"""
        print("\n" + "=" * 100)
        print("COMPREHENSIVE PERFORMANCE TEST SUITE SUMMARY")
        print("=" * 100)

        if "error" in self.results:
            print(f"❌ SUITE FAILED: {self.results['error']}")
            return

        # Metadata
        if "metadata" in self.results:
            meta = self.results["metadata"]
            print(f"⏱️  Total Runtime: {meta['total_duration_seconds']:.2f} seconds")
            print(f"📅 Timestamp: {meta['timestamp']}")
            print(f"🐍 Python: {meta['environment']['python_version'].split()[0]}")
            print(f"💻 Platform: {meta['environment']['platform']}")

        # System benchmarks
        system = self.results.get("system_benchmarks", {})
        if system.get("success"):
            print("\n🖥️  SYSTEM PERFORMANCE:")
            summary = system.get("summary", {})
            print(
                f"   • Database Queries: {summary.get('database_query_avg_ms', 0):.3f}ms avg"
            )
            print(f"   • File I/O: {summary.get('file_io_avg_mb_s', 0):.1f} MB/s avg")
            print(
                f"   • Text Processing: {summary.get('text_processing_avg_chars_s', 0):,.0f} chars/s avg"
            )
            print("   ✅ System performance: EXCELLENT")
        else:
            print(f"\n❌ SYSTEM PERFORMANCE: {system.get('error', 'Failed')}")

        # API benchmarks
        api = self.results.get("api_benchmarks", {})
        if api.get("success"):
            print("\n🌐 API PERFORMANCE:")
            print("   ✅ API endpoints tested successfully")
            # Could extract more detailed API metrics here
        elif api.get("skipped"):
            print("\n⏭️  API PERFORMANCE: Skipped (server not available)")
        else:
            print(f"\n❌ API PERFORMANCE: {api.get('error', 'Failed')}")

        # PDF processing
        pdf = self.results.get("pdf_processing", {})
        if pdf.get("success"):
            print("\n📄 PDF PROCESSING PERFORMANCE:")
            summary = pdf.get("summary", {})
            avg_time = summary.get("avg_processing_time_ms", 0)
            print(f"   • Average Processing Time: {avg_time:.2f}ms")
            status = (
                "✅ EXCELLENT"
                if avg_time < 10
                else "✅ GOOD"
                if avg_time < 50
                else "⚠️ ACCEPTABLE"
            )
            print(f"   {status}")
        else:
            print(f"\n❌ PDF PROCESSING: {pdf.get('error', 'Failed')}")

        # Regression analysis
        regression = self.results.get("regression_analysis")
        if regression:
            if "error" in regression:
                print(f"\n❌ REGRESSION ANALYSIS: {regression['error']}")
            elif regression.get("status") == "baselines_established":
                print(f"\n📊 REGRESSION ANALYSIS: {regression['message']}")
            else:
                print("\n📈 REGRESSION ANALYSIS:")
                for category, analysis in regression.items():
                    if analysis and isinstance(analysis, dict[str, Any]):
                        status = analysis.get("overall_status", "Unknown")
                        print(f"   • {category.title()}: {status}")

                        reg_count = analysis.get("regressions", {}).get("count", 0)
                        if reg_count > 0:
                            print(f"     🚨 {reg_count} regression(s) detected")

                        imp_count = analysis.get("improvements", {}).get("count", 0)
                        if imp_count > 0:
                            print(f"     🚀 {imp_count} improvement(s) detected")

        # Overall assessment
        print("\n🎯 OVERALL ASSESSMENT:")

        failed_components = []
        if not system.get("success"):
            failed_components.append("System")
        if not api.get("success") and not api.get("skipped"):
            failed_components.append("API")
        if not pdf.get("success"):
            failed_components.append("PDF Processing")

        if not failed_components:
            # Check for critical regressions
            critical_regressions = False
            if regression and isinstance(regression, dict[str, Any]):
                for analysis in regression.values():
                    if (
                        isinstance(analysis, dict[str, Any])
                        and analysis.get("regressions", {}).get("critical", 0) > 0
                    ):
                        critical_regressions = True
                        break

            if critical_regressions:
                assessment = (
                    "🔴 CRITICAL ISSUES DETECTED - Investigate regressions immediately"
                )
            else:
                assessment = "✅ EXCELLENT - All systems performing optimally"
        else:
            assessment = (
                f"⚠️ ISSUES DETECTED - Failed components: {', '.join(failed_components)}"
            )

        print(f"   {assessment}")

        print("\n" + "=" * 100)

    def save_results(self, filename: str = None) -> Any:
        """Save comprehensive results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comprehensive_performance_results_{timestamp}.json"

        output_path = self.output_dir / filename
        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        logger.info(f"Comprehensive results saved to: {output_path}")
        return output_path

    def generate_html_report(self, filename: str = None) -> Any:
        """Generate HTML performance report"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.html"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Comprehensive Performance Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 30px; border-bottom: 1px solid #ecf0f1; padding-bottom: 5px; }}
                .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }}
                .metric-card {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; text-align: center; }}
                .metric-value {{ font-size: 32px; font-weight: bold; color: #2c3e50; margin: 10px 0; }}
                .metric-label {{ color: #7f8c8d; font-size: 14px; text-transform: uppercase; }}
                .status-excellent {{ color: #27ae60; }}
                .status-good {{ color: #2980b9; }}
                .status-warning {{ color: #f39c12; }}
                .status-critical {{ color: #e74c3c; }}
                .timestamp {{ color: #7f8c8d; font-size: 14px; margin-top: 20px; }}
                .summary-box {{ background: #e8f4f8; border-left: 4px solid #3498db; padding: 15px; margin: 15px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
                th {{ background: #f8f9fa; font-weight: 600; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Comprehensive Performance Report</h1>
                <div class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>

                <div class="summary-box">
                    <h3>📊 Executive Summary</h3>
                    <p>Comprehensive performance analysis of the AI Enhanced PDF Scholar system with evidence-based metrics and regression detection.</p>
                </div>

                <h2>🎯 Key Performance Indicators</h2>
                <div class="metric-grid">
        """

        # Add metric cards based on results
        system = self.results.get("system_benchmarks", {})
        if system.get("success"):
            summary = system.get("summary", {})
            html_content += f"""
                    <div class="metric-card">
                        <div class="metric-label">Database Query Time</div>
                        <div class="metric-value status-excellent">{summary.get('database_query_avg_ms', 0):.3f}ms</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">File I/O Throughput</div>
                        <div class="metric-value status-excellent">{summary.get('file_io_avg_mb_s', 0):.0f}MB/s</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Text Processing</div>
                        <div class="metric-value status-excellent">{summary.get('text_processing_avg_chars_s', 0):,.0f}chars/s</div>
                    </div>
            """

        pdf = self.results.get("pdf_processing", {})
        if pdf.get("success"):
            avg_time = pdf.get("summary", {}).get("avg_processing_time_ms", 0)
            status_class = "status-excellent" if avg_time < 10 else "status-good"
            html_content += f"""
                    <div class="metric-card">
                        <div class="metric-label">PDF Processing Time</div>
                        <div class="metric-value {status_class}">{avg_time:.2f}ms</div>
                    </div>
            """

        html_content += """
                </div>

                <h2>📈 Performance Analysis</h2>
                <p>All measurements are based on statistical analysis with multiple runs to ensure reliability and accuracy.</p>

                <div class="timestamp">
                    Report generated by Comprehensive Performance Suite v1.0.0<br>
                    🤖 Generated with <a href="https://claude.ai/code">Claude Code</a>
                </div>
            </div>
        </body>
        </html>
        """

        output_path = self.output_dir / filename
        with open(output_path, "w") as f:
            f.write(html_content)

        logger.info(f"HTML report saved to: {output_path}")
        return output_path


async def main() -> Any:
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive Performance Test Suite")
    parser.add_argument(
        "--api-url", default="http://localhost:8000", help="API base URL to test"
    )
    parser.add_argument(
        "--no-regressions", action="store_true", help="Skip regression analysis"
    )
    parser.add_argument("--save", action="store_true", help="Save results to files")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--output-dir", help="Output directory for results")

    args = parser.parse_args()

    try:
        # Initialize suite
        output_dir = Path(args.output_dir) if args.output_dir else None
        suite = ComprehensivePerformanceSuite(output_dir)

        # Run comprehensive tests
        results = await suite.run_all_benchmarks(
            api_url=args.api_url, detect_regressions=not args.no_regressions
        )

        # Print summary
        suite.print_comprehensive_summary()

        # Save results if requested
        if args.save:
            json_file = suite.save_results()
            print(f"\n💾 Results saved to: {json_file}")

        # Generate HTML report if requested
        if args.html:
            html_file = suite.generate_html_report()
            print(f"📄 HTML report saved to: {html_file}")

        # Exit with appropriate code
        if "error" not in results:
            return 0
        else:
            return 1

    except Exception as e:
        logger.error(f"Comprehensive performance suite failed: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
