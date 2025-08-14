"""
Complete System Integration End-to-End Testing
Comprehensive end-to-end testing of the entire AI Enhanced PDF Scholar system
including all agent components, workflows, and production readiness validation.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

import pytest
import httpx
from fastapi.testclient import TestClient

# Import all test suites
from tests.production.test_production_readiness import test_complete_production_readiness
from tests.load.test_production_load import test_complete_load_testing_suite
from tests.resilience.test_fault_tolerance import test_complete_fault_tolerance_suite
from tests.security.test_sql_injection_comprehensive import test_complete_sql_injection_protection
from tests.security.test_xss_comprehensive import test_complete_xss_protection
from tests.performance.test_regression import test_complete_performance_regression

# Import application components
from backend.api.main import app

logger = logging.getLogger(__name__)


@dataclass
class SystemIntegrationResult:
    """Result of a system integration test."""
    test_suite_name: str
    passed: bool
    score: float
    duration_seconds: float
    critical_issues: List[str]
    details: Dict[str, Any]
    error_message: Optional[str] = None


class CompleteSystemIntegrationTestSuite:
    """
    Master test suite that orchestrates all production readiness testing
    and validates complete system integration across all components.
    """

    def __init__(self):
        """Initialize complete system integration test suite."""
        self.client = TestClient(app)
        self.integration_results = []
        self.start_time = None

        # Define test suite execution order and requirements
        self.test_suites = [
            {
                "name": "production_readiness",
                "description": "Agent A1, A2, A3 integration validation",
                "function": test_complete_production_readiness,
                "required_score": 95.0,
                "critical": True,
                "timeout_seconds": 300
            },
            {
                "name": "security_sql_injection",
                "description": "SQL injection protection validation",
                "function": test_complete_sql_injection_protection,
                "required_score": 95.0,
                "critical": True,
                "timeout_seconds": 600
            },
            {
                "name": "security_xss_protection",
                "description": "XSS protection validation",
                "function": test_complete_xss_protection,
                "required_score": 95.0,
                "critical": True,
                "timeout_seconds": 600
            },
            {
                "name": "performance_regression",
                "description": "Performance benchmarks and regression testing",
                "function": test_complete_performance_regression,
                "required_score": 80.0,
                "critical": True,
                "timeout_seconds": 900
            },
            {
                "name": "fault_tolerance",
                "description": "System resilience and fault tolerance",
                "function": test_complete_fault_tolerance_suite,
                "required_score": 80.0,
                "critical": False,
                "timeout_seconds": 800
            },
            {
                "name": "load_testing",
                "description": "Production load testing (1000+ users)",
                "function": test_complete_load_testing_suite,
                "required_score": 90.0,
                "critical": False,
                "timeout_seconds": 1200
            }
        ]

    async def run_system_health_check(self) -> Dict[str, Any]:
        """Run comprehensive system health check before integration tests."""
        logger.info("Running comprehensive system health check")

        health_results = {
            "overall_healthy": True,
            "component_health": {},
            "warnings": [],
            "errors": []
        }

        try:
            # Test basic API connectivity
            response = self.client.get("/api/system/health")
            api_healthy = response.status_code == 200
            health_results["component_health"]["api"] = {
                "healthy": api_healthy,
                "response_code": response.status_code,
                "response_time_ms": 0  # Would measure actual response time
            }

            if not api_healthy:
                health_results["errors"].append(f"API health check failed: {response.status_code}")
                health_results["overall_healthy"] = False

            # Test database connectivity (through API)
            try:
                response = self.client.get("/api/documents")
                db_healthy = response.status_code in [200, 404]  # 404 is OK (no documents)
                health_results["component_health"]["database"] = {
                    "healthy": db_healthy,
                    "response_code": response.status_code
                }

                if not db_healthy:
                    health_results["errors"].append(f"Database connectivity issue: {response.status_code}")
            except Exception as e:
                health_results["component_health"]["database"] = {"healthy": False, "error": str(e)}
                health_results["errors"].append(f"Database connection failed: {e}")
                health_results["overall_healthy"] = False

            # Test document library functionality
            try:
                response = self.client.get("/api/library/documents")
                library_healthy = response.status_code in [200, 404]
                health_results["component_health"]["library"] = {
                    "healthy": library_healthy,
                    "response_code": response.status_code
                }

                if not library_healthy:
                    health_results["warnings"].append(f"Document library issue: {response.status_code}")
            except Exception as e:
                health_results["component_health"]["library"] = {"healthy": False, "error": str(e)}
                health_results["warnings"].append(f"Document library issue: {e}")

            # Test RAG system
            try:
                response = self.client.post("/api/rag/query", json={"query": "system test"})
                rag_healthy = response.status_code in [200, 404, 422]  # Various acceptable responses
                health_results["component_health"]["rag"] = {
                    "healthy": rag_healthy,
                    "response_code": response.status_code
                }

                if not rag_healthy and response.status_code >= 500:
                    health_results["warnings"].append(f"RAG system issue: {response.status_code}")
            except Exception as e:
                health_results["component_health"]["rag"] = {"healthy": False, "error": str(e)}
                health_results["warnings"].append(f"RAG system issue: {e}")

        except Exception as e:
            health_results["errors"].append(f"System health check failed: {e}")
            health_results["overall_healthy"] = False

        logger.info(f"System health check: {'HEALTHY' if health_results['overall_healthy'] else 'ISSUES DETECTED'}")
        if health_results["errors"]:
            for error in health_results["errors"]:
                logger.error(f"Health check error: {error}")
        if health_results["warnings"]:
            for warning in health_results["warnings"]:
                logger.warning(f"Health check warning: {warning}")

        return health_results

    async def run_test_suite_with_timeout(
        self,
        suite_config: Dict[str, Any]
    ) -> SystemIntegrationResult:
        """Run a test suite with timeout and error handling."""

        logger.info(f"Starting test suite: {suite_config['name']}")
        suite_start_time = time.time()

        try:
            # Run test suite with timeout
            test_task = asyncio.create_task(suite_config["function"]())

            try:
                result = await asyncio.wait_for(test_task, timeout=suite_config["timeout_seconds"])
            except asyncio.TimeoutError:
                test_task.cancel()
                raise Exception(f"Test suite timed out after {suite_config['timeout_seconds']} seconds")

            # Extract score and details from result
            if isinstance(result, dict):
                # Try to find score in various possible result structures
                score = 0.0
                details = result

                # Common score field patterns
                score_fields = [
                    "production_readiness_score",
                    "sql_injection_test_summary.overall_protection_rate",
                    "xss_test_summary.overall_protection_rate",
                    "performance_regression_summary.performance_score",
                    "fault_tolerance_results.successful_scenarios"
                ]

                for field in score_fields:
                    if "." in field:
                        # Nested field
                        parts = field.split(".")
                        value = result
                        try:
                            for part in parts:
                                value = value[part]
                            if isinstance(value, (int, float)):
                                if field.endswith("successful_scenarios"):
                                    # Convert count to percentage (assuming some total)
                                    total_field = field.replace("successful_scenarios", "total_scenarios")
                                    total_parts = total_field.split(".")
                                    total_value = result
                                    for part in total_parts:
                                        total_value = total_value[part]
                                    score = (value / total_value) * 100 if total_value > 0 else 0
                                else:
                                    score = float(value)
                                break
                        except (KeyError, TypeError):
                            continue
                    else:
                        # Top-level field
                        if field in result:
                            score = float(result[field])
                            break

                # Check if score meets requirements
                passed = score >= suite_config["required_score"]
                critical_issues = []

                if not passed:
                    critical_issues.append(f"Score {score:.1f}% below required {suite_config['required_score']:.1f}%")

                # Look for critical issues in result
                if "critical_vulnerabilities" in result:
                    crit_vulns = result["critical_vulnerabilities"]
                    if isinstance(crit_vulns, list) and len(crit_vulns) > 0:
                        critical_issues.extend([f"Critical vulnerability: {v}" for v in crit_vulns[:3]])
                    elif isinstance(crit_vulns, int) and crit_vulns > 0:
                        critical_issues.append(f"{crit_vulns} critical vulnerabilities found")

                return SystemIntegrationResult(
                    test_suite_name=suite_config["name"],
                    passed=passed,
                    score=score,
                    duration_seconds=time.time() - suite_start_time,
                    critical_issues=critical_issues,
                    details=details
                )

            else:
                # Simple boolean or other result type
                passed = bool(result)
                score = 100.0 if passed else 0.0

                return SystemIntegrationResult(
                    test_suite_name=suite_config["name"],
                    passed=passed,
                    score=score,
                    duration_seconds=time.time() - suite_start_time,
                    critical_issues=[] if passed else ["Test suite returned failure"],
                    details={"result": result}
                )

        except Exception as e:
            logger.error(f"Test suite {suite_config['name']} failed: {e}")
            return SystemIntegrationResult(
                test_suite_name=suite_config["name"],
                passed=False,
                score=0.0,
                duration_seconds=time.time() - suite_start_time,
                critical_issues=[f"Test execution failed: {str(e)}"],
                details={},
                error_message=str(e)
            )

    async def run_end_to_end_workflow_test(self) -> Dict[str, Any]:
        """Test complete end-to-end user workflow."""
        logger.info("Running end-to-end workflow test")

        workflow_start = time.time()
        workflow_steps = []

        try:
            # Step 1: Health check
            step_start = time.time()
            health_response = self.client.get("/api/system/health")
            workflow_steps.append({
                "step": "system_health_check",
                "success": health_response.status_code == 200,
                "duration_ms": (time.time() - step_start) * 1000,
                "response_code": health_response.status_code
            })

            # Step 2: Document library access
            step_start = time.time()
            library_response = self.client.get("/api/library/documents")
            workflow_steps.append({
                "step": "library_access",
                "success": library_response.status_code in [200, 404],
                "duration_ms": (time.time() - step_start) * 1000,
                "response_code": library_response.status_code
            })

            # Step 3: Document upload simulation
            step_start = time.time()
            test_content = "Test document content for end-to-end workflow testing."
            files = {"file": ("workflow_test.pdf", test_content.encode(), "application/pdf")}

            try:
                upload_response = self.client.post("/api/documents/upload", files=files)
                upload_success = upload_response.status_code < 500  # Allow various responses
                workflow_steps.append({
                    "step": "document_upload",
                    "success": upload_success,
                    "duration_ms": (time.time() - step_start) * 1000,
                    "response_code": upload_response.status_code
                })
            except Exception as e:
                workflow_steps.append({
                    "step": "document_upload",
                    "success": False,
                    "duration_ms": (time.time() - step_start) * 1000,
                    "error": str(e)
                })

            # Step 4: RAG query simulation
            step_start = time.time()
            try:
                rag_response = self.client.post("/api/rag/query", json={
                    "query": "What is the content of the uploaded document?"
                })
                rag_success = rag_response.status_code < 500  # Allow various responses
                workflow_steps.append({
                    "step": "rag_query",
                    "success": rag_success,
                    "duration_ms": (time.time() - step_start) * 1000,
                    "response_code": rag_response.status_code
                })
            except Exception as e:
                workflow_steps.append({
                    "step": "rag_query",
                    "success": False,
                    "duration_ms": (time.time() - step_start) * 1000,
                    "error": str(e)
                })

            # Step 5: Document search
            step_start = time.time()
            try:
                search_response = self.client.get("/api/documents", params={"search": "test"})
                search_success = search_response.status_code in [200, 404]
                workflow_steps.append({
                    "step": "document_search",
                    "success": search_success,
                    "duration_ms": (time.time() - step_start) * 1000,
                    "response_code": search_response.status_code
                })
            except Exception as e:
                workflow_steps.append({
                    "step": "document_search",
                    "success": False,
                    "duration_ms": (time.time() - step_start) * 1000,
                    "error": str(e)
                })

            # Calculate overall workflow success
            successful_steps = len([s for s in workflow_steps if s["success"]])
            total_steps = len(workflow_steps)
            workflow_success_rate = (successful_steps / total_steps) * 100

            total_duration = time.time() - workflow_start

            workflow_result = {
                "workflow_success": workflow_success_rate >= 80.0,  # 80% of steps must succeed
                "success_rate": workflow_success_rate,
                "total_duration_seconds": total_duration,
                "steps": workflow_steps,
                "successful_steps": successful_steps,
                "total_steps": total_steps
            }

            logger.info(f"End-to-end workflow test: {workflow_success_rate:.1f}% success rate")
            return workflow_result

        except Exception as e:
            logger.error(f"End-to-end workflow test failed: {e}")
            return {
                "workflow_success": False,
                "success_rate": 0.0,
                "total_duration_seconds": time.time() - workflow_start,
                "error": str(e),
                "steps": workflow_steps
            }

    async def run_complete_system_integration(self) -> Dict[str, Any]:
        """Run complete system integration testing."""
        logger.info("Starting complete system integration testing")
        self.start_time = time.time()

        integration_summary = {
            "overall_success": False,
            "production_ready": False,
            "total_duration_seconds": 0,
            "test_suites_executed": 0,
            "test_suites_passed": 0,
            "critical_test_suites_passed": 0,
            "critical_issues": [],
            "warnings": [],
            "test_timestamp": datetime.utcnow().isoformat()
        }

        try:
            # Step 1: System health check
            logger.info("=== Phase 1: System Health Check ===")
            health_results = await self.run_system_health_check()

            if not health_results["overall_healthy"]:
                integration_summary["critical_issues"].extend(health_results["errors"])
                integration_summary["warnings"].extend(health_results["warnings"])
                logger.error("System health check failed - aborting integration tests")
                return integration_summary

            integration_summary["system_health"] = health_results

            # Step 2: End-to-end workflow test
            logger.info("=== Phase 2: End-to-End Workflow Test ===")
            workflow_results = await self.run_end_to_end_workflow_test()

            integration_summary["workflow_test"] = workflow_results

            if not workflow_results["workflow_success"]:
                integration_summary["warnings"].append("End-to-end workflow test failed")

            # Step 3: Run all test suites
            logger.info("=== Phase 3: Comprehensive Test Suite Execution ===")

            for suite_config in self.test_suites:
                logger.info(f"--- Running {suite_config['name']}: {suite_config['description']} ---")

                suite_result = await self.run_test_suite_with_timeout(suite_config)
                self.integration_results.append(suite_result)

                integration_summary["test_suites_executed"] += 1

                if suite_result.passed:
                    integration_summary["test_suites_passed"] += 1

                    if suite_config["critical"]:
                        integration_summary["critical_test_suites_passed"] += 1

                    logger.info(f"✓ {suite_config['name']} PASSED (score: {suite_result.score:.1f}%)")
                else:
                    logger.error(f"✗ {suite_config['name']} FAILED (score: {suite_result.score:.1f}%)")

                    if suite_config["critical"]:
                        integration_summary["critical_issues"].extend(suite_result.critical_issues)
                    else:
                        integration_summary["warnings"].extend(suite_result.critical_issues)

                # Add detailed results
                integration_summary[f"{suite_config['name']}_results"] = {
                    "passed": suite_result.passed,
                    "score": suite_result.score,
                    "duration_seconds": suite_result.duration_seconds,
                    "critical_issues": suite_result.critical_issues,
                    "error_message": suite_result.error_message
                }

            # Calculate overall results
            total_duration = time.time() - self.start_time
            integration_summary["total_duration_seconds"] = total_duration

            # Determine overall success
            critical_suites_count = len([s for s in self.test_suites if s["critical"]])
            overall_success = (
                health_results["overall_healthy"] and
                integration_summary["critical_test_suites_passed"] == critical_suites_count and
                len(integration_summary["critical_issues"]) == 0
            )

            integration_summary["overall_success"] = overall_success

            # Determine production readiness
            # Require: all critical tests passed + >90% non-critical tests passed
            non_critical_suites = [s for s in self.integration_results if not self._is_critical_suite(s.test_suite_name)]
            non_critical_passed = len([s for s in non_critical_suites if s.passed])
            non_critical_total = len(non_critical_suites)
            non_critical_success_rate = (non_critical_passed / non_critical_total * 100) if non_critical_total > 0 else 100

            production_ready = (
                overall_success and
                non_critical_success_rate >= 90.0 and
                workflow_results["workflow_success"]
            )

            integration_summary["production_ready"] = production_ready
            integration_summary["non_critical_success_rate"] = non_critical_success_rate

            # Generate final assessment
            if production_ready:
                logger.info("🎉 SYSTEM INTEGRATION COMPLETE - PRODUCTION READY")
            elif overall_success:
                logger.info("✅ SYSTEM INTEGRATION COMPLETE - MOSTLY READY (minor issues)")
            else:
                logger.error("❌ SYSTEM INTEGRATION FAILED - NOT PRODUCTION READY")

            return integration_summary

        except Exception as e:
            logger.error(f"System integration testing failed: {e}")
            integration_summary["critical_issues"].append(f"Integration test execution failed: {e}")
            integration_summary["total_duration_seconds"] = time.time() - self.start_time
            return integration_summary

    def _is_critical_suite(self, suite_name: str) -> bool:
        """Check if a test suite is marked as critical."""
        for suite_config in self.test_suites:
            if suite_config["name"] == suite_name:
                return suite_config["critical"]
        return False


@pytest.mark.asyncio
@pytest.mark.integration
class TestCompleteSystemIntegration:
    """Complete system integration testing."""

    @pytest.fixture(autouse=True)
    async def setup_system_integration_test(self):
        """Set up system integration testing environment."""
        self.test_suite = CompleteSystemIntegrationTestSuite()
        yield

    async def test_system_health_check(self):
        """Test comprehensive system health check."""
        health_results = await self.test_suite.run_system_health_check()

        # System should be healthy before integration tests
        assert health_results["overall_healthy"], f"System health issues: {health_results['errors']}"

        # Core components should be functional
        assert health_results["component_health"]["api"]["healthy"], "API not healthy"

        logger.info("System health check PASSED")

    async def test_end_to_end_workflow(self):
        """Test complete end-to-end user workflow."""
        workflow_results = await self.test_suite.run_end_to_end_workflow_test()

        # Workflow should have reasonable success rate
        assert workflow_results["success_rate"] >= 60.0, f"Workflow success rate too low: {workflow_results['success_rate']:.1f}%"

        # Critical steps should work
        critical_steps = ["system_health_check", "library_access"]
        for step in workflow_results["steps"]:
            if step["step"] in critical_steps:
                assert step["success"], f"Critical workflow step failed: {step['step']}"

        logger.info("End-to-end workflow test PASSED")

    async def test_production_readiness_integration(self):
        """Test production readiness integration."""
        # This test is handled by the complete integration suite
        # Just ensure the test suite can be initialized
        assert self.test_suite is not None
        assert len(self.test_suite.test_suites) > 0

        logger.info("Production readiness integration test structure PASSED")


@pytest.mark.asyncio
async def test_complete_system_integration_suite():
    """Run the complete system integration test suite."""
    logger.info("Starting complete system integration test suite")

    # Initialize the master test suite
    integration_suite = CompleteSystemIntegrationTestSuite()

    # Run complete system integration
    results = await integration_suite.run_complete_system_integration()

    # Save comprehensive results
    results_file = "performance_results/complete_system_integration_results.json"
    os.makedirs(os.path.dirname(results_file), exist_ok=True)

    # Make results serializable
    serializable_results = json.loads(json.dumps(results, default=str))

    with open(results_file, 'w') as f:
        json.dump(serializable_results, f, indent=2)

    # Validate results
    assert results["overall_success"], f"System integration failed: {results['critical_issues']}"

    # Check production readiness
    production_ready = results["production_ready"]
    if not production_ready:
        logger.warning("System not fully production ready, but core functionality working")
        logger.warning(f"Issues: {results['critical_issues']}")

    # Validate critical test suites
    critical_suites = ["production_readiness", "security_sql_injection", "security_xss_protection", "performance_regression"]

    for suite_name in critical_suites:
        suite_results = results.get(f"{suite_name}_results", {})
        assert suite_results.get("passed", False), f"Critical test suite failed: {suite_name}"

    logger.info("=== COMPLETE SYSTEM INTEGRATION RESULTS ===")
    logger.info(f"Overall Success: {'YES' if results['overall_success'] else 'NO'}")
    logger.info(f"Production Ready: {'YES' if results['production_ready'] else 'NO'}")
    logger.info(f"Test Suites Passed: {results['test_suites_passed']}/{results['test_suites_executed']}")
    logger.info(f"Critical Issues: {len(results['critical_issues'])}")
    logger.info(f"Warnings: {len(results['warnings'])}")
    logger.info(f"Total Duration: {results['total_duration_seconds']:.1f} seconds")
    logger.info(f"Results saved to: {results_file}")

    if results["critical_issues"]:
        logger.error("Critical Issues Found:")
        for issue in results["critical_issues"][:5]:  # Show first 5 critical issues
            logger.error(f"  - {issue}")

    if results["warnings"]:
        logger.warning("Warnings:")
        for warning in results["warnings"][:5]:  # Show first 5 warnings
            logger.warning(f"  - {warning}")

    return results


if __name__ == "__main__":
    """Run complete system integration tests standalone."""
    import asyncio

    async def main():
        results = await test_complete_system_integration_suite()

        print("\n" + "="*60)
        print("COMPLETE SYSTEM INTEGRATION TEST RESULTS")
        print("="*60)
        print(f"Overall Success: {'✅ YES' if results['overall_success'] else '❌ NO'}")
        print(f"Production Ready: {'✅ YES' if results['production_ready'] else '❌ NO'}")
        print(f"Test Suites: {results['test_suites_passed']}/{results['test_suites_executed']} passed")
        print(f"Duration: {results['total_duration_seconds']:.1f} seconds")
        print(f"Critical Issues: {len(results['critical_issues'])}")
        print(f"Warnings: {len(results['warnings'])}")
        print("="*60)

        return results

    asyncio.run(main())