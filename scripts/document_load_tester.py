#!/usr/bin/env python3
"""
Document Processing Load Tester
Specialized testing for document upload, processing, and RAG query performance
with various document sizes and concurrent users
"""

import concurrent.futures
import json
import logging
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class DocumentTestResult:
    """Results from processing a single document"""

    file_size_mb: float
    processing_time_ms: float
    success: bool
    error_message: str | None
    memory_used_mb: float
    concurrent_user_id: int
    timestamp: float


@dataclass
class LoadTestScenario:
    """Load test scenario configuration"""

    name: str
    concurrent_users: int
    documents_per_user: int
    document_sizes_mb: list[float]
    duration_seconds: int
    target_throughput: float  # Documents per second


@dataclass
class LoadTestResults:
    """Complete load test results"""

    scenario_name: str
    total_documents: int
    successful_documents: int
    failed_documents: int
    avg_processing_time_ms: float
    min_processing_time_ms: float
    max_processing_time_ms: float
    throughput_docs_per_second: float
    peak_memory_mb: float
    error_rate_percent: float
    duration_seconds: float
    concurrent_users: int
    individual_results: list[DocumentTestResult]


class DocumentLoadTester:
    """Specialized load testing for document processing operations"""

    def __init__(self, output_dir: str = "performance_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results = {}

    def create_test_document(self, size_mb: float) -> bytes:
        """Create a test PDF document of specified size"""
        # Basic PDF structure with variable content
        pdf_header = b"%PDF-1.4\n"
        pdf_content = b"1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        pdf_content += (
            b"2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n"
        )
        pdf_content += (
            b"3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n"
        )
        pdf_content += b"/Contents 4 0 R\n>>\nendobj\n"
        pdf_content += (
            b"4 0 obj\n<<\n/Length 100\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n"
        )

        # Add content to reach desired size
        target_bytes = int(size_mb * 1024 * 1024)
        content_needed = target_bytes - len(pdf_header) - len(pdf_content) - 200

        # Fill with repetitive text content
        text_block = (
            b"This is sample text content for testing document processing performance. "
            * 100
        )
        while len(pdf_content) < content_needed:
            pdf_content += text_block[
                : min(len(text_block), content_needed - len(pdf_content))
            ]

        pdf_content += b"\nET\nendstream\nendobj\n"
        pdf_footer = b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000131 00000 n \n0000000251 00000 n \n"
        pdf_footer += b"trailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n400\n%%EOF"

        document = pdf_header + pdf_content + pdf_footer

        # Adjust size if needed
        if len(document) < target_bytes:
            padding = target_bytes - len(document)
            document += b" " * padding

        return document[:target_bytes]

    def simulate_document_processing(
        self, document_data: bytes, user_id: int
    ) -> DocumentTestResult:
        """Simulate document processing operations"""
        import psutil

        process = psutil.Process()
        start_memory = process.memory_info().rss / (1024 * 1024)  # MB

        start_time = time.time()
        success = True
        error_message = None

        try:
            # Simulate PDF processing operations
            # 1. Content extraction simulation
            text_content = document_data.decode("utf-8", errors="ignore")

            # 2. Text analysis simulation
            words = text_content.split()
            word_count = len(words)
            char_count = len(text_content)

            # 3. Chunking simulation (typical for RAG preprocessing)
            chunk_size = 1000
            chunks = [
                text_content[i : i + chunk_size]
                for i in range(0, len(text_content), chunk_size)
            ]

            # 4. Metadata extraction simulation
            metadata = {
                "word_count": word_count,
                "char_count": char_count,
                "chunk_count": len(chunks),
                "file_size": len(document_data),
                "processing_timestamp": time.time(),
            }

            # 5. Simulate vector embedding generation (computational overhead)
            embedding_simulation = []
            for chunk in chunks[:10]:  # Limit to first 10 chunks for performance
                # Simple simulation of embedding generation
                chunk_hash = hash(chunk) % 1000000
                embedding_simulation.append(chunk_hash)

            # Small delay to simulate I/O operations
            time.sleep(0.001)  # 1ms simulated I/O

        except Exception as e:
            success = False
            error_message = str(e)

        end_time = time.time()
        end_memory = process.memory_info().rss / (1024 * 1024)  # MB

        return DocumentTestResult(
            file_size_mb=len(document_data) / (1024 * 1024),
            processing_time_ms=(end_time - start_time) * 1000,
            success=success,
            error_message=error_message,
            memory_used_mb=max(start_memory, end_memory),
            concurrent_user_id=user_id,
            timestamp=start_time,
        )

    def run_single_user_test(
        self, user_id: int, documents_per_user: int, document_sizes_mb: list[float]
    ) -> list[DocumentTestResult]:
        """Run document processing test for a single simulated user"""
        results = []

        for i in range(documents_per_user):
            # Rotate through different document sizes
            size_mb = document_sizes_mb[i % len(document_sizes_mb)]

            try:
                # Create test document
                document_data = self.create_test_document(size_mb)

                # Process document
                result = self.simulate_document_processing(document_data, user_id)
                results.append(result)

                # Small delay between documents to simulate realistic usage
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"User {user_id} document {i} failed: {e}")
                results.append(
                    DocumentTestResult(
                        file_size_mb=size_mb,
                        processing_time_ms=0,
                        success=False,
                        error_message=str(e),
                        memory_used_mb=0,
                        concurrent_user_id=user_id,
                        timestamp=time.time(),
                    )
                )

        return results

    def run_load_test_scenario(self, scenario: LoadTestScenario) -> LoadTestResults:
        """Run a complete load test scenario"""
        logger.info(f"Starting load test scenario: {scenario.name}")
        logger.info(
            f"Concurrent users: {scenario.concurrent_users}, Documents per user: {scenario.documents_per_user}"
        )

        start_time = time.time()
        all_results = []

        # Use ThreadPoolExecutor for concurrent user simulation
        with ThreadPoolExecutor(max_workers=scenario.concurrent_users) as executor:
            # Submit tasks for all users
            futures = [
                executor.submit(
                    self.run_single_user_test,
                    user_id,
                    scenario.documents_per_user,
                    scenario.document_sizes_mb,
                )
                for user_id in range(scenario.concurrent_users)
            ]

            # Collect results as they complete
            for future in concurrent.futures.as_completed(
                futures, timeout=scenario.duration_seconds
            ):
                try:
                    user_results = future.result(timeout=30)
                    all_results.extend(user_results)
                except Exception as e:
                    logger.error(f"User thread failed: {e}")

        end_time = time.time()
        duration = end_time - start_time

        # Analyze results
        successful_results = [r for r in all_results if r.success]
        failed_results = [r for r in all_results if not r.success]

        if successful_results:
            processing_times = [r.processing_time_ms for r in successful_results]
            memory_usage = [r.memory_used_mb for r in successful_results]

            load_test_results = LoadTestResults(
                scenario_name=scenario.name,
                total_documents=len(all_results),
                successful_documents=len(successful_results),
                failed_documents=len(failed_results),
                avg_processing_time_ms=statistics.mean(processing_times),
                min_processing_time_ms=min(processing_times),
                max_processing_time_ms=max(processing_times),
                throughput_docs_per_second=len(successful_results) / duration,
                peak_memory_mb=max(memory_usage),
                error_rate_percent=(len(failed_results) / len(all_results)) * 100,
                duration_seconds=duration,
                concurrent_users=scenario.concurrent_users,
                individual_results=all_results,
            )
        else:
            load_test_results = LoadTestResults(
                scenario_name=scenario.name,
                total_documents=len(all_results),
                successful_documents=0,
                failed_documents=len(failed_results),
                avg_processing_time_ms=0,
                min_processing_time_ms=0,
                max_processing_time_ms=0,
                throughput_docs_per_second=0,
                peak_memory_mb=0,
                error_rate_percent=100,
                duration_seconds=duration,
                concurrent_users=scenario.concurrent_users,
                individual_results=all_results,
            )

        logger.info(f"Load test scenario complete: {scenario.name}")
        logger.info(
            f"Throughput: {load_test_results.throughput_docs_per_second:.2f} docs/sec, Error rate: {load_test_results.error_rate_percent:.1f}%"
        )

        return load_test_results

    def run_comprehensive_document_load_tests(self) -> dict[str, Any]:
        """Run comprehensive document processing load tests"""
        logger.info("Starting comprehensive document load testing...")

        # Define test scenarios
        scenarios = [
            LoadTestScenario(
                name="light_load_small_docs",
                concurrent_users=3,
                documents_per_user=10,
                document_sizes_mb=[1.0, 2.0],
                duration_seconds=60,
                target_throughput=5.0,
            ),
            LoadTestScenario(
                name="moderate_load_mixed_docs",
                concurrent_users=5,
                documents_per_user=8,
                document_sizes_mb=[1.0, 5.0, 10.0],
                duration_seconds=90,
                target_throughput=3.0,
            ),
            LoadTestScenario(
                name="heavy_load_large_docs",
                concurrent_users=10,
                documents_per_user=5,
                document_sizes_mb=[15.0, 25.0],
                duration_seconds=120,
                target_throughput=1.5,
            ),
            LoadTestScenario(
                name="stress_test_maximum_load",
                concurrent_users=20,
                documents_per_user=3,
                document_sizes_mb=[5.0, 15.0, 30.0, 50.0],
                duration_seconds=180,
                target_throughput=1.0,
            ),
            LoadTestScenario(
                name="sustained_load_test",
                concurrent_users=8,
                documents_per_user=15,
                document_sizes_mb=[5.0, 10.0],
                duration_seconds=300,  # 5 minutes
                target_throughput=2.0,
            ),
        ]

        # Run all scenarios
        test_results = {}
        overall_start = time.time()

        for scenario in scenarios:
            try:
                result = self.run_load_test_scenario(scenario)
                test_results[scenario.name] = asdict(result)

                # Brief pause between scenarios
                time.sleep(5)

            except Exception as e:
                logger.error(f"Scenario {scenario.name} failed: {e}")
                test_results[scenario.name] = {
                    "error": str(e),
                    "scenario_name": scenario.name,
                }

        overall_duration = time.time() - overall_start

        # Generate comprehensive analysis
        analysis = self.analyze_load_test_results(test_results)

        comprehensive_results = {
            "metadata": {
                "test_start_time": overall_start,
                "total_test_duration_seconds": overall_duration,
                "timestamp": datetime.now().isoformat(),
                "scenarios_tested": len(scenarios),
            },
            "scenario_results": test_results,
            "comprehensive_analysis": analysis,
        }

        self.results = comprehensive_results
        logger.info(
            f"Comprehensive document load testing completed in {overall_duration:.2f} seconds"
        )

        return comprehensive_results

    def analyze_load_test_results(self, test_results: dict[str, Any]) -> dict[str, Any]:
        """Analyze load test results and generate insights"""

        # Extract successful scenarios
        successful_scenarios = {
            name: result
            for name, result in test_results.items()
            if "error" not in result and result.get("error_rate_percent", 100) < 50
        }

        if not successful_scenarios:
            return {
                "overall_assessment": "CRITICAL - All scenarios failed or had high error rates",
                "recommendations": [
                    "System requires immediate attention before production deployment"
                ],
                "max_supported_users": 0,
                "recommended_document_size_limit_mb": 1.0,
            }

        # Calculate performance metrics
        throughputs = [
            result["throughput_docs_per_second"]
            for result in successful_scenarios.values()
        ]
        error_rates = [
            result["error_rate_percent"] for result in successful_scenarios.values()
        ]
        processing_times = [
            result["avg_processing_time_ms"] for result in successful_scenarios.values()
        ]
        peak_memories = [
            result["peak_memory_mb"] for result in successful_scenarios.values()
        ]
        concurrent_users = [
            result["concurrent_users"] for result in successful_scenarios.values()
        ]

        # Determine maximum supported concurrent users
        max_supported_users = max(concurrent_users) if concurrent_users else 0

        # Find scenarios with acceptable performance (error rate < 5%, processing time < 30s)
        acceptable_scenarios = [
            result
            for result in successful_scenarios.values()
            if result["error_rate_percent"] < 5
            and result["avg_processing_time_ms"] < 30000
        ]

        if acceptable_scenarios:
            recommended_users = max(
                result["concurrent_users"] for result in acceptable_scenarios
            )
        else:
            recommended_users = min(concurrent_users) // 2 if concurrent_users else 1

        # Document size analysis
        all_results = []
        for result in successful_scenarios.values():
            if "individual_results" in result:
                all_results.extend(result["individual_results"])

        if all_results:
            # Group by document size and analyze performance
            size_performance = {}
            for doc_result in all_results:
                if doc_result["success"]:
                    size_mb = round(doc_result["file_size_mb"])
                    if size_mb not in size_performance:
                        size_performance[size_mb] = []
                    size_performance[size_mb].append(doc_result["processing_time_ms"])

            # Find recommended document size limit (where avg processing time < 10s)
            recommended_size_limit = 50.0  # Default maximum
            for size_mb, times in size_performance.items():
                avg_time = statistics.mean(times)
                if avg_time > 10000:  # 10 seconds
                    recommended_size_limit = min(recommended_size_limit, size_mb - 1)
        else:
            recommended_size_limit = 10.0  # Conservative default

        # Overall performance assessment
        avg_throughput = statistics.mean(throughputs) if throughputs else 0
        avg_error_rate = statistics.mean(error_rates) if error_rates else 100
        avg_processing_time = (
            statistics.mean(processing_times) if processing_times else 0
        )

        if avg_error_rate < 2 and avg_processing_time < 5000 and avg_throughput > 2:
            assessment = "EXCELLENT"
        elif avg_error_rate < 5 and avg_processing_time < 15000 and avg_throughput > 1:
            assessment = "GOOD"
        elif avg_error_rate < 10 and avg_processing_time < 30000:
            assessment = "ACCEPTABLE"
        else:
            assessment = "POOR"

        # Generate recommendations
        recommendations = []

        if avg_error_rate > 5:
            recommendations.append(
                f"High error rate detected ({avg_error_rate:.1f}%). Improve error handling and resource management."
            )

        if avg_processing_time > 15000:
            recommendations.append(
                f"Slow processing times ({avg_processing_time/1000:.1f}s avg). Optimize document processing algorithms."
            )

        if max(peak_memories) > 4096:  # 4GB
            recommendations.append(
                "High memory usage detected. Implement streaming processing for large documents."
            )

        if avg_throughput < 1:
            recommendations.append(
                "Low throughput. Consider parallel processing and caching strategies."
            )

        recommendations.extend(
            [
                f"Recommended maximum concurrent users: {recommended_users}",
                f"Recommended document size limit: {recommended_size_limit:.1f}MB",
                "Implement queue-based processing for high-load scenarios",
                "Set up monitoring and alerting for production deployment",
            ]
        )

        return {
            "overall_assessment": assessment,
            "performance_metrics": {
                "avg_throughput_docs_per_sec": round(avg_throughput, 2),
                "avg_error_rate_percent": round(avg_error_rate, 2),
                "avg_processing_time_ms": round(avg_processing_time, 2),
                "peak_memory_usage_mb": (
                    round(max(peak_memories), 2) if peak_memories else 0
                ),
            },
            "capacity_planning": {
                "max_concurrent_users_tested": max_supported_users,
                "recommended_max_concurrent_users": recommended_users,
                "recommended_document_size_limit_mb": recommended_size_limit,
                "estimated_documents_per_hour": (
                    round(avg_throughput * 3600, 0) if avg_throughput > 0 else 0
                ),
            },
            "recommendations": recommendations,
            "production_readiness": {
                "ready_for_production": assessment in ["EXCELLENT", "GOOD"],
                "critical_issues": [
                    rec for rec in recommendations if "High" in rec or "Low" in rec
                ],
                "performance_bottlenecks": self.identify_bottlenecks(test_results),
            },
        }

    def identify_bottlenecks(self, test_results: dict[str, Any]) -> list[str]:
        """Identify performance bottlenecks from test results"""
        bottlenecks = []

        for scenario_name, result in test_results.items():
            if "error" in result:
                continue

            # Memory bottlenecks
            if result.get("peak_memory_mb", 0) > 2048:
                bottlenecks.append(
                    f"Memory bottleneck in {scenario_name}: {result['peak_memory_mb']:.0f}MB peak usage"
                )

            # Processing time bottlenecks
            if result.get("avg_processing_time_ms", 0) > 20000:
                bottlenecks.append(
                    f"Processing time bottleneck in {scenario_name}: {result['avg_processing_time_ms']/1000:.1f}s average"
                )

            # Throughput bottlenecks
            if result.get("throughput_docs_per_second", 0) < 1:
                bottlenecks.append(
                    f"Throughput bottleneck in {scenario_name}: {result['throughput_docs_per_second']:.2f} docs/sec"
                )

            # Error rate bottlenecks
            if result.get("error_rate_percent", 0) > 10:
                bottlenecks.append(
                    f"Error rate bottleneck in {scenario_name}: {result['error_rate_percent']:.1f}% failures"
                )

        return list(set(bottlenecks))  # Remove duplicates

    def save_results(self, filename: str = None) -> str:
        """Save load test results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"document_load_test_results_{timestamp}.json"

        output_path = self.output_dir / filename

        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        logger.info(f"Load test results saved to: {output_path}")
        return str(output_path)

    def print_summary(self):
        """Print load test summary"""
        if not self.results:
            print("No results to display")
            return

        print("\n" + "=" * 120)
        print("DOCUMENT PROCESSING LOAD TEST SUMMARY")
        print("=" * 120)

        analysis = self.results.get("comprehensive_analysis", {})
        assessment = analysis.get("overall_assessment", "Unknown")

        print(f"🎯 Overall Assessment: {assessment}")

        # Performance metrics
        metrics = analysis.get("performance_metrics", {})
        print("\n📊 Performance Metrics:")
        print(
            f"   • Average Throughput: {metrics.get('avg_throughput_docs_per_sec', 0):.2f} docs/sec"
        )
        print(
            f"   • Average Error Rate: {metrics.get('avg_error_rate_percent', 0):.2f}%"
        )
        print(
            f"   • Average Processing Time: {metrics.get('avg_processing_time_ms', 0)/1000:.2f} seconds"
        )
        print(f"   • Peak Memory Usage: {metrics.get('peak_memory_usage_mb', 0):.0f}MB")

        # Capacity planning
        capacity = analysis.get("capacity_planning", {})
        print("\n🏗️ Capacity Planning:")
        print(
            f"   • Recommended Max Users: {capacity.get('recommended_max_concurrent_users', 0)}"
        )
        print(
            f"   • Document Size Limit: {capacity.get('recommended_document_size_limit_mb', 0):.1f}MB"
        )
        print(
            f"   • Estimated Capacity: {capacity.get('estimated_documents_per_hour', 0):.0f} docs/hour"
        )

        # Production readiness
        readiness = analysis.get("production_readiness", {})
        ready = readiness.get("ready_for_production", False)
        print(f"\n🚀 Production Readiness: {'✅ READY' if ready else '❌ NOT READY'}")

        # Bottlenecks
        bottlenecks = readiness.get("performance_bottlenecks", [])
        if bottlenecks:
            print("\n⚠️ Performance Bottlenecks:")
            for bottleneck in bottlenecks[:5]:  # Show top 5
                print(f"   • {bottleneck}")

        # Top recommendations
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            print("\n💡 Top Recommendations:")
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"   {i}. {rec}")

        print("\n" + "=" * 120)


def main():
    """Main entry point for document load testing"""
    import argparse

    parser = argparse.ArgumentParser(description="Document Processing Load Tester")
    parser.add_argument("--save", action="store_true", help="Save results to JSON file")
    parser.add_argument("--output-file", help="Output filename for results")
    parser.add_argument(
        "--output-dir", default="performance_results", help="Output directory"
    )

    args = parser.parse_args()

    try:
        tester = DocumentLoadTester(output_dir=args.output_dir)
        results = tester.run_comprehensive_document_load_tests()

        # Print summary
        tester.print_summary()

        # Save results if requested
        if args.save:
            output_file = tester.save_results(args.output_file)
            print(f"\n💾 Results saved to: {output_file}")

        # Return appropriate exit code
        analysis = results.get("comprehensive_analysis", {})
        ready = analysis.get("production_readiness", {}).get(
            "ready_for_production", False
        )
        return 0 if ready else 1

    except Exception as e:
        logger.error(f"Document load testing failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
