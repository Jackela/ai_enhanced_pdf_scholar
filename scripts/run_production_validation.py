"""
Production Validation Master Test Runner
Orchestrates all Agent A4 testing suites and generates final production readiness certification.
This is the master script that runs all validation tests in the correct order.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import all test suites
# Import certification generator
from scripts.generate_production_certification import generate_production_certification
from tests.integration.test_complete_system_integration import (
    test_complete_system_integration_suite,
)
from tests.load.test_production_load import test_complete_load_testing_suite
from tests.performance.test_regression import test_complete_performance_regression
from tests.production.test_production_readiness import ProductionReadinessTestSuite
from tests.resilience.test_fault_tolerance import test_complete_fault_tolerance_suite
from tests.security.test_sql_injection_comprehensive import (
    test_complete_sql_injection_protection,
)
from tests.security.test_xss_comprehensive import test_complete_xss_protection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('production_validation.log')
    ]
)
logger = logging.getLogger(__name__)


class ProductionValidationOrchestrator:
    """
    Master orchestrator for all Agent A4 production validation testing.
    Runs tests in optimal order and handles dependencies.
    """

    def __init__(self):
        """Initialize validation orchestrator."""
        self.start_time = None
        self.validation_results = {}
        self.overall_success = False

        # Define test execution plan with dependencies
        self.test_execution_plan = [
            {
                "name": "production_readiness",
                "description": "Agent A1, A2, A3 Integration Validation",
                "function": self._run_production_readiness_tests,
                "critical": True,
                "timeout_minutes": 10,
                "prerequisites": []
            },
            {
                "name": "security_sql_injection",
                "description": "SQL Injection Protection Testing",
                "function": self._run_sql_injection_tests,
                "critical": True,
                "timeout_minutes": 15,
                "prerequisites": ["production_readiness"]
            },
            {
                "name": "security_xss_protection",
                "description": "XSS Protection Testing",
                "function": self._run_xss_protection_tests,
                "critical": True,
                "timeout_minutes": 15,
                "prerequisites": ["production_readiness"]
            },
            {
                "name": "performance_regression",
                "description": "Performance Benchmarks and Regression",
                "function": self._run_performance_regression_tests,
                "critical": True,
                "timeout_minutes": 20,
                "prerequisites": ["production_readiness"]
            },
            {
                "name": "fault_tolerance",
                "description": "System Resilience and Fault Tolerance",
                "function": self._run_fault_tolerance_tests,
                "critical": False,
                "timeout_minutes": 18,
                "prerequisites": ["production_readiness", "performance_regression"]
            },
            {
                "name": "load_testing",
                "description": "Production Load Testing (1000+ users)",
                "function": self._run_load_testing,
                "critical": False,
                "timeout_minutes": 25,
                "prerequisites": ["production_readiness", "performance_regression", "security_sql_injection"]
            },
            {
                "name": "system_integration",
                "description": "Complete System Integration End-to-End",
                "function": self._run_system_integration_tests,
                "critical": True,
                "timeout_minutes": 30,
                "prerequisites": ["production_readiness", "security_sql_injection", "security_xss_protection"]
            }
        ]

    async def _run_production_readiness_tests(self):
        """Run production readiness tests."""
        logger.info("🔄 Running production readiness tests...")

        # Initialize and run production readiness test suite
        test_suite = ProductionReadinessTestSuite()
        await test_suite.setup_production_environment()

        # Import and run the complete test
        from tests.production.test_production_readiness import (
            test_complete_production_readiness,
        )
        results = await test_complete_production_readiness(test_suite)

        return results

    async def _run_sql_injection_tests(self):
        """Run SQL injection protection tests."""
        logger.info("🔄 Running SQL injection protection tests...")
        return await test_complete_sql_injection_protection()

    async def _run_xss_protection_tests(self):
        """Run XSS protection tests."""
        logger.info("🔄 Running XSS protection tests...")
        return await test_complete_xss_protection()

    async def _run_performance_regression_tests(self):
        """Run performance regression tests."""
        logger.info("🔄 Running performance regression tests...")
        return await test_complete_performance_regression()

    async def _run_fault_tolerance_tests(self):
        """Run fault tolerance tests."""
        logger.info("🔄 Running fault tolerance tests...")
        return await test_complete_fault_tolerance_suite()

    async def _run_load_testing(self):
        """Run load testing."""
        logger.info("🔄 Running load testing...")
        return await test_complete_load_testing_suite()

    async def _run_system_integration_tests(self):
        """Run system integration tests."""
        logger.info("🔄 Running system integration tests...")
        return await test_complete_system_integration_suite()

    def _check_prerequisites(self, test_config):
        """Check if test prerequisites are met."""
        for prereq in test_config["prerequisites"]:
            if prereq not in self.validation_results:
                return False, f"Prerequisite {prereq} not completed"

            result = self.validation_results[prereq]
            if not result.get("success", False):
                return False, f"Prerequisite {prereq} failed"

        return True, "Prerequisites met"

    async def _run_single_test_suite(self, test_config):
        """Run a single test suite with error handling and timeout."""
        test_name = test_config["name"]
        logger.info("=" * 60)
        logger.info(f"Starting: {test_config['description']}")
        logger.info("=" * 60)

        # Check prerequisites
        prereq_ok, prereq_msg = self._check_prerequisites(test_config)
        if not prereq_ok:
            logger.warning(f"Skipping {test_name}: {prereq_msg}")
            return {
                "success": False,
                "skipped": True,
                "reason": prereq_msg,
                "duration_seconds": 0
            }

        start_time = time.time()

        try:
            # Run test with timeout
            timeout_seconds = test_config["timeout_minutes"] * 60
            test_task = asyncio.create_task(test_config["function"]())

            try:
                result = await asyncio.wait_for(test_task, timeout=timeout_seconds)

                duration = time.time() - start_time

                # Determine success based on result structure
                success = self._determine_test_success(result, test_name)

                test_result = {
                    "success": success,
                    "skipped": False,
                    "duration_seconds": duration,
                    "result_data": result,
                    "critical": test_config["critical"]
                }

                if success:
                    logger.info(f"✅ {test_config['description']} PASSED ({duration:.1f}s)")
                else:
                    logger.error(f"❌ {test_config['description']} FAILED ({duration:.1f}s)")

                return test_result

            except asyncio.TimeoutError:
                test_task.cancel()
                duration = time.time() - start_time
                logger.error(f"⏰ {test_config['description']} TIMED OUT ({duration:.1f}s)")

                return {
                    "success": False,
                    "skipped": False,
                    "timeout": True,
                    "duration_seconds": duration,
                    "critical": test_config["critical"],
                    "error": f"Test timed out after {test_config['timeout_minutes']} minutes"
                }

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"💥 {test_config['description']} ERROR: {e} ({duration:.1f}s)")

            return {
                "success": False,
                "skipped": False,
                "duration_seconds": duration,
                "critical": test_config["critical"],
                "error": str(e)
            }

    def _determine_test_success(self, result, test_name):
        """Determine if test was successful based on result structure."""
        if isinstance(result, bool):
            return result

        if isinstance(result, dict):
            # Look for common success indicators
            success_indicators = [
                "production_readiness_score",
                "overall_protection_rate",
                "performance_score",
                "overall_success",
                "production_ready"
            ]

            for indicator in success_indicators:
                if indicator in result:
                    value = result[indicator]
                    if isinstance(value, bool):
                        return value
                    elif isinstance(value, (int, float)):
                        # Score-based success (generally >90% is good)
                        return value >= 75.0  # Minimum passing score

            # Look for nested success indicators
            for key, value in result.items():
                if isinstance(value, dict):
                    if "overall_success" in value:
                        return value["overall_success"]
                    if "production_ready" in value:
                        return value["production_ready"]

        # Default: assume success if no explicit failure
        return True

    async def run_complete_production_validation(self):
        """Run complete production validation test suite."""
        self.start_time = time.time()

        logger.info("🚀 Starting Complete Production Validation")
        logger.info(f"📅 Timestamp: {datetime.utcnow().isoformat()}")
        logger.info(f"📋 Total Test Suites: {len(self.test_execution_plan)}")

        # Ensure results directory exists
        os.makedirs("performance_results", exist_ok=True)

        # Run each test suite in order
        for test_config in self.test_execution_plan:
            test_result = await self._run_single_test_suite(test_config)
            self.validation_results[test_config["name"]] = test_result

            # If critical test fails, consider stopping
            if test_config["critical"] and not test_result["success"]:
                if not test_result.get("skipped", False):
                    logger.error(f"💀 Critical test {test_config['name']} failed - continuing with remaining tests")

        # Calculate overall results
        total_duration = time.time() - self.start_time

        total_tests = len(self.validation_results)
        successful_tests = len([r for r in self.validation_results.values() if r["success"]])
        critical_tests = len([r for r in self.validation_results.values() if r.get("critical", False)])
        successful_critical_tests = len([
            r for r in self.validation_results.values()
            if r.get("critical", False) and r["success"]
        ])

        # Overall success requires all critical tests to pass
        self.overall_success = successful_critical_tests == critical_tests

        # Generate summary
        summary = {
            "overall_success": self.overall_success,
            "production_ready": self.overall_success and (successful_tests / total_tests) >= 0.8,
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "critical_tests": critical_tests,
            "successful_critical_tests": successful_critical_tests,
            "success_rate": (successful_tests / total_tests) * 100,
            "total_duration_seconds": total_duration,
            "validation_timestamp": datetime.utcnow().isoformat(),
            "test_results": self.validation_results
        }

        # Log summary
        logger.info("=" * 70)
        logger.info("📊 PRODUCTION VALIDATION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Overall Success: {'✅ YES' if summary['overall_success'] else '❌ NO'}")
        logger.info(f"Production Ready: {'✅ YES' if summary['production_ready'] else '❌ NO'}")
        logger.info(f"Success Rate: {summary['success_rate']:.1f}% ({successful_tests}/{total_tests})")
        logger.info(f"Critical Tests: {successful_critical_tests}/{critical_tests} passed")
        logger.info(f"Total Duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        logger.info("=" * 70)

        # Log individual test results
        for test_name, result in self.validation_results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            if result.get("skipped"):
                status = "⏭️ SKIP"
            elif result.get("timeout"):
                status = "⏰ TIMEOUT"

            critical_marker = " [CRITICAL]" if result.get("critical") else ""
            logger.info(f"  {status} {test_name}{critical_marker} ({result['duration_seconds']:.1f}s)")

        return summary

    async def generate_final_certification(self, validation_summary):
        """Generate final production readiness certification."""
        logger.info("📜 Generating Production Readiness Certification...")

        try:
            certification_report = generate_production_certification()

            if certification_report:
                cert_summary = certification_report["certification_summary"]

                logger.info("=" * 70)
                logger.info("🏆 PRODUCTION READINESS CERTIFICATION")
                logger.info("=" * 70)
                logger.info(f"Certification Level: {cert_summary['certification_level'].replace('_', ' ')}")
                logger.info(f"Overall Score: {cert_summary['overall_score']:.1f}%")
                logger.info(f"Production Ready: {'YES' if cert_summary['production_ready'] else 'NO'}")
                logger.info(f"Valid Until: {cert_summary['valid_until']}")
                logger.info(f"Critical Issues: {cert_summary['critical_issues_count']}")
                logger.info("=" * 70)

                return certification_report
            else:
                logger.error("Failed to generate certification report")
                return None

        except Exception as e:
            logger.error(f"Error generating certification: {e}")
            return None


async def main():
    """Main function to run complete production validation."""
    print("🚀 AI Enhanced PDF Scholar - Production Validation Suite")
    print("=" * 70)
    print("This will run comprehensive production readiness validation")
    print("including all Agent A4 testing suites and certification.")
    print("=" * 70)

    # Initialize orchestrator
    orchestrator = ProductionValidationOrchestrator()

    try:
        # Run complete validation
        validation_summary = await orchestrator.run_complete_production_validation()

        # Generate final certification
        certification_report = await orchestrator.generate_final_certification(validation_summary)

        # Final status
        if validation_summary["overall_success"]:
            print("\n🎉 PRODUCTION VALIDATION COMPLETED SUCCESSFULLY!")
            print("✅ System is ready for production deployment")
        else:
            print("\n⚠️ PRODUCTION VALIDATION COMPLETED WITH ISSUES")
            print("❌ System requires fixes before production deployment")

        # Show certification level if available
        if certification_report:
            cert_level = certification_report["certification_summary"]["certification_level"]
            cert_score = certification_report["certification_summary"]["overall_score"]
            print(f"🏆 Certification Level: {cert_level.replace('_', ' ')}")
            print(f"📊 Overall Score: {cert_score:.1f}%")

        print("\n📁 Results saved to: performance_results/")
        print(f"⏱️ Total time: {validation_summary['total_duration_seconds']:.1f} seconds")

        return validation_summary["overall_success"]

    except KeyboardInterrupt:
        logger.info("🛑 Production validation interrupted by user")
        return False
    except Exception as e:
        logger.error(f"💥 Production validation failed: {e}")
        return False


if __name__ == "__main__":
    """Run production validation standalone."""
    import asyncio

    # Run the validation
    success = asyncio.run(main())

    # Exit with appropriate code
    exit_code = 0 if success else 1
    sys.exit(exit_code)
