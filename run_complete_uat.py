#!/usr/bin/env python3
"""
Complete UAT Execution Script for Multi-Document RAG System
===========================================================

Orchestrates comprehensive User Acceptance Testing including:
1. Backend service validation with real PDF documents
2. API endpoint testing with HTTP requests
3. End-to-end workflow validation
4. Performance and quality assessment
5. Integration and compatibility testing

This script provides a complete validation suite to ensure the
multi-document RAG system is production-ready.

Usage:
    python run_complete_uat.py [--skip-api] [--skip-pdf] [--quick]
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UATOrchestrator:
    """Orchestrate complete UAT execution"""

    def __init__(self, args):
        self.args = args
        self.start_time = datetime.now()
        self.results: dict[str, Any] = {
            'tests': {},
            'summary': {},
            'performance': {},
            'quality': {}
        }
        self.api_server_process = None

    def check_prerequisites(self) -> bool:
        """Check system prerequisites for UAT"""
        logger.info("Checking UAT prerequisites...")

        prerequisites = []

        # Check Python version
        if sys.version_info >= (3, 8):
            prerequisites.append(("Python >= 3.8", True, f"Python {sys.version_info.major}.{sys.version_info.minor}"))
        else:
            prerequisites.append(("Python >= 3.8", False, f"Python {sys.version_info.major}.{sys.version_info.minor}"))

        # Check required modules
        required_modules = [
            'fastapi', 'hypercorn', 'pydantic', 'sqlalchemy',
            'aiohttp', 'pytest', 'asyncio'
        ]

        for module in required_modules:
            try:
                __import__(module)
                prerequisites.append((f"Module: {module}", True, "Available"))
            except ImportError:
                prerequisites.append((f"Module: {module}", False, "Missing"))

        # Check database
        try:
            from src.database.connection import DatabaseConnection
            db = DatabaseConnection(":memory:")  # Use memory database for testing
            prerequisites.append(("Database Connection", True, "Available"))
        except Exception as e:
            prerequisites.append(("Database Connection", False, f"Error: {e}"))

        # Display results
        print("\n" + "=" * 60)
        print("UAT PREREQUISITES CHECK")
        print("=" * 60)

        all_passed = True
        for name, passed, details in prerequisites:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} {name}: {details}")
            if not passed:
                all_passed = False

        if not all_passed:
            print("\n⚠️  Some prerequisites failed. UAT may not work correctly.")

        return all_passed

    async def start_api_server(self) -> bool:
        """Start API server for testing"""
        if self.args.skip_api:
            logger.info("Skipping API server startup (--skip-api)")
            return True

        logger.info("Starting API server for UAT...")

        try:
            # Kill any stale processes on port 8000 first
            if sys.platform == "win32":
                # Windows: Find and kill processes using port 8000
                import subprocess
                try:
                    result = subprocess.run(
                        'netstat -ano | findstr :8000',
                        shell=True,
                        capture_output=True,
                        text=True
                    )
                    if result.stdout:
                        pids = set()
                        for line in result.stdout.splitlines():
                            parts = line.split()
                            if len(parts) > 4 and parts[-1].isdigit():
                                pids.add(parts[-1])
                        if pids:
                            logger.info(f"Killing stale processes on port 8000: {pids}")
                            for pid in pids:
                                subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                except:
                    pass  # Ignore errors, proceed anyway

            # Check if server is already running
            import aiohttp
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get('http://127.0.0.1:8000/api/system/health', timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status == 200:
                            logger.info("API server already running")
                            return True
                except:
                    pass

            # Start API server using direct script with Hypercorn
            logger.info("Starting API server with Hypercorn for better Windows compatibility...")
            cmd = [
                sys.executable,
                'start_api_server.py'
            ]

            # Capture output for debugging but prevent deadlock
            self.api_server_process = subprocess.Popen(
                cmd,
                cwd=project_root,
                stdout=subprocess.PIPE,  # Capture for debugging
                stderr=subprocess.PIPE,  # Capture for debugging
                text=True
            )

            # Check if process actually started
            await asyncio.sleep(5)  # Give it more time to start with Hypercorn
            if self.api_server_process.poll() is not None:
                # Process died immediately
                stdout, stderr = self.api_server_process.communicate()
                logger.error(f"Server process died immediately. Exit code: {self.api_server_process.returncode}")
                if stdout:
                    logger.error(f"Stdout: {stdout[:2000]}")  # Show more output
                if stderr:
                    logger.error(f"Stderr: {stderr[:2000]}")  # Show more error output
                return False
            else:
                # Process is running, but let's check its output
                import time
                time.sleep(2)
                # Try to read some output without blocking
                try:
                    import select
                    if sys.platform != "win32":
                        # Unix-like systems
                        readable, _, _ = select.select([self.api_server_process.stdout], [], [], 0)
                        if readable:
                            output = self.api_server_process.stdout.read(1000)
                            logger.info(f"Server output: {output}")
                except:
                    pass  # Not critical if we can't read output

            # Wait for server to start
            logger.info("Waiting for API server to become ready...")
            for i in range(40):  # Increased from 30 to 40 seconds
                # Check if process is still alive
                if self.api_server_process.poll() is not None:
                    stdout, stderr = self.api_server_process.communicate()
                    logger.error(f"Server process died during startup. Exit code: {self.api_server_process.returncode}")
                    if stdout:
                        logger.error(f"Stdout: {stdout[:1000]}")
                    if stderr:
                        logger.error(f"Stderr: {stderr[:1000]}")
                    return False

                try:
                    async with aiohttp.ClientSession() as session:
                        # Try multiple URLs to maximize compatibility
                        urls_to_try = [
                            'http://127.0.0.1:8000/api/system/health',
                            'http://localhost:8000/api/system/health',
                            'http://0.0.0.0:8000/api/system/health'
                        ]

                        for url in urls_to_try:
                            try:
                                async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
                                    if response.status == 200:
                                        logger.info(f"✅ API server started successfully at {url}")
                                        return True
                                    elif response.status == 500:
                                        logger.warning(f"Server responded with 500 at {url}, may have startup issues")
                            except aiohttp.ClientConnectorError:
                                continue  # Connection refused, server not ready yet
                            except Exception as e:
                                logger.debug(f"Error checking {url}: {e}")
                                continue
                except Exception as e:
                    logger.debug(f"Error during health check attempt {i+1}: {e}")

                if i % 5 == 0 and i > 0:
                    logger.info(f"Still waiting for API server... ({i} seconds elapsed)")

                await asyncio.sleep(1)

            logger.error("API server failed to start within timeout")
            return False

        except Exception as e:
            logger.error(f"Failed to start API server: {e}")
            return False

    def stop_api_server(self):
        """Stop API server"""
        if self.api_server_process:
            logger.info("Stopping API server...")
            try:
                # Check if process is still running
                if self.api_server_process.poll() is None:
                    # Try graceful shutdown first
                    self.api_server_process.terminate()
                    try:
                        self.api_server_process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        # Force kill if needed
                        logger.warning("API server did not terminate gracefully, forcing kill...")
                        self.api_server_process.kill()
                        self.api_server_process.wait(timeout=5)
                else:
                    logger.info("API server already stopped")
            except Exception as e:
                logger.error(f"Error stopping API server: {e}")

            self.api_server_process = None

    async def run_backend_uat(self) -> dict[str, Any]:
        """Run backend service UAT"""
        logger.info("Running backend service UAT...")

        try:
            # Import and run backend UAT
            from tests.uat_multi_document_system import MultiDocumentUATSuite

            uat_suite = MultiDocumentUATSuite()
            result = await uat_suite.run_full_uat_suite()

            self.results['tests']['backend'] = result

            return result

        except Exception as e:
            logger.error(f"Backend UAT failed: {e}")
            return {
                'summary': {'success_rate': 0, 'total_tests': 0, 'passed': 0, 'failed': 1},
                'error': str(e)
            }

    async def run_api_uat(self) -> dict[str, Any]:
        """Run API endpoint UAT"""
        if self.args.skip_api:
            logger.info("Skipping API UAT (--skip-api)")
            return {'summary': {'success_rate': 100, 'total_tests': 0, 'passed': 0, 'failed': 0}}

        logger.info("Running API endpoint UAT...")

        try:
            from tests.uat_api_endpoints import MultiDocumentAPIUATSuite

            uat_suite = MultiDocumentAPIUATSuite()
            result = await uat_suite.run_full_api_uat_suite()

            self.results['tests']['api'] = result

            return result

        except Exception as e:
            logger.error(f"API UAT failed: {e}")
            return {
                'summary': {'success_rate': 0, 'total_tests': 0, 'passed': 0, 'failed': 1},
                'error': str(e)
            }

    async def run_pdf_workflow_uat(self) -> dict[str, Any]:
        """Run real PDF workflow UAT"""
        if self.args.skip_pdf:
            logger.info("Skipping PDF workflow UAT (--skip-pdf)")
            return {'summary': {'success_rate': 100, 'total_tests': 0, 'passed': 0, 'failed': 0}}

        logger.info("Running real PDF workflow UAT...")

        try:
            from tests.uat_real_pdf_workflow import RealPDFWorkflowUATSuite

            uat_suite = RealPDFWorkflowUATSuite()
            result = await uat_suite.run_full_real_pdf_uat_suite()

            self.results['tests']['pdf_workflow'] = result

            return result

        except Exception as e:
            logger.error(f"PDF workflow UAT failed: {e}")
            return {
                'summary': {'success_rate': 0, 'total_tests': 0, 'passed': 0, 'failed': 1},
                'error': str(e)
            }

    def run_unit_tests(self) -> dict[str, Any]:
        """Run existing unit tests"""
        logger.info("Running unit tests...")

        try:
            # Run pytest on the tests directory
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', 'tests/', '-v', '--tb=short'],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            # Parse pytest output for test counts
            output_lines = result.stdout.split('\n')
            summary_line = next((line for line in output_lines if 'passed' in line and ('failed' in line or 'error' in line or 'skipped' in line)), '')

            # Extract test counts (simplified parsing)
            passed = failed = skipped = 0
            if 'passed' in summary_line:
                import re
                passed_match = re.search(r'(\d+) passed', summary_line)
                failed_match = re.search(r'(\d+) failed', summary_line)
                skipped_match = re.search(r'(\d+) skipped', summary_line)

                passed = int(passed_match.group(1)) if passed_match else 0
                failed = int(failed_match.group(1)) if failed_match else 0
                skipped = int(skipped_match.group(1)) if skipped_match else 0

            total = passed + failed + skipped
            success_rate = (passed / total * 100) if total > 0 else 100

            return {
                'summary': {
                    'total_tests': total,
                    'passed': passed,
                    'failed': failed,
                    'skipped': skipped,
                    'success_rate': success_rate
                },
                'return_code': result.returncode,
                'output': result.stdout,
                'errors': result.stderr
            }

        except Exception as e:
            logger.error(f"Unit tests failed: {e}")
            return {
                'summary': {'success_rate': 0, 'total_tests': 0, 'passed': 0, 'failed': 1},
                'error': str(e)
            }

    def generate_comprehensive_report(self) -> dict[str, Any]:
        """Generate comprehensive UAT report"""
        total_duration = (datetime.now() - self.start_time).total_seconds()

        # Aggregate results
        total_tests = 0
        total_passed = 0
        total_failed = 0

        test_summaries = {}

        for test_type, result in self.results['tests'].items():
            if 'summary' in result:
                summary = result['summary']
                test_summaries[test_type] = summary
                total_tests += summary.get('total_tests', 0)
                total_passed += summary.get('passed', 0)
                total_failed += summary.get('failed', 0)

        # Add unit tests if available
        if 'unit_tests' in self.results:
            unit_summary = self.results['unit_tests']['summary']
            test_summaries['unit_tests'] = unit_summary
            total_tests += unit_summary.get('total_tests', 0)
            total_passed += unit_summary.get('passed', 0)
            total_failed += unit_summary.get('failed', 0)

        overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

        # Determine overall status
        if overall_success_rate >= 95:
            overall_status = "EXCELLENT"
        elif overall_success_rate >= 90:
            overall_status = "GOOD"
        elif overall_success_rate >= 80:
            overall_status = "ACCEPTABLE"
        elif overall_success_rate >= 60:
            overall_status = "NEEDS_IMPROVEMENT"
        else:
            overall_status = "CRITICAL_ISSUES"

        return {
            'overall_status': overall_status,
            'overall_success_rate': overall_success_rate,
            'total_duration': total_duration,
            'test_summaries': test_summaries,
            'totals': {
                'total_tests': total_tests,
                'total_passed': total_passed,
                'total_failed': total_failed
            },
            'detailed_results': self.results,
            'timestamp': datetime.now().isoformat(),
            'system_info': {
                'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                'platform': sys.platform,
                'project_root': str(project_root)
            }
        }

    async def run_complete_uat_suite(self):
        """Run the complete UAT suite"""
        print("🚀 Multi-Document RAG System - Complete UAT Suite")
        print("=" * 60)
        print(f"Start Time: {self.start_time}")
        print(f"Mode: {'Quick' if self.args.quick else 'Comprehensive'}")
        print(f"Skipping: API={self.args.skip_api}, PDF={self.args.skip_pdf}")
        print()

        try:
            # Check prerequisites
            if not self.check_prerequisites():
                print("\n⚠️  Prerequisites check failed. Continuing anyway...")

            # Start API server if needed
            if not await self.start_api_server():
                print("\n❌ Failed to start API server. Some tests may fail.")

            # Run unit tests first
            print("\n" + "=" * 50)
            print("RUNNING UNIT TESTS")
            print("=" * 50)
            self.results['unit_tests'] = self.run_unit_tests()

            # Run backend UAT
            print("\n" + "=" * 50)
            print("RUNNING BACKEND SERVICE UAT")
            print("=" * 50)
            backend_result = await self.run_backend_uat()

            # Run API UAT
            print("\n" + "=" * 50)
            print("RUNNING API ENDPOINT UAT")
            print("=" * 50)
            api_result = await self.run_api_uat()

            # Run PDF workflow UAT
            print("\n" + "=" * 50)
            print("RUNNING REAL PDF WORKFLOW UAT")
            print("=" * 50)
            pdf_result = await self.run_pdf_workflow_uat()

            # Generate comprehensive report
            comprehensive_report = self.generate_comprehensive_report()

            # Save detailed report
            report_file = project_root / "complete_uat_report.json"
            with open(report_file, 'w') as f:
                json.dump(comprehensive_report, f, indent=2)

            # Display final summary
            self.display_final_summary(comprehensive_report)

            return comprehensive_report

        except KeyboardInterrupt:
            print("\n⚠️  UAT interrupted by user")
            return None
        except Exception as e:
            logger.error(f"Critical UAT failure: {e}")
            print(f"\n❌ Critical UAT failure: {e}")
            return None
        finally:
            # Always clean up
            self.stop_api_server()

    def display_final_summary(self, report: dict[str, Any]):
        """Display final UAT summary"""
        print("\n" + "=" * 60)
        print("🎯 COMPLETE UAT SUMMARY")
        print("=" * 60)

        # Overall status
        status_emoji = {
            "EXCELLENT": "🟢",
            "GOOD": "🟡",
            "ACCEPTABLE": "🟠",
            "NEEDS_IMPROVEMENT": "🔴",
            "CRITICAL_ISSUES": "💀"
        }

        emoji = status_emoji.get(report['overall_status'], "❓")
        print(f"Overall Status: {emoji} {report['overall_status']}")
        print(f"Success Rate: {report['overall_success_rate']:.1f}%")
        print(f"Total Duration: {report['total_duration']:.1f} seconds")
        print(f"Total Tests: {report['totals']['total_tests']}")
        print(f"Passed: {report['totals']['total_passed']}")
        print(f"Failed: {report['totals']['total_failed']}")

        # Test category breakdown
        print("\nTEST CATEGORY BREAKDOWN")
        print("-" * 40)
        for category, summary in report['test_summaries'].items():
            rate = summary.get('success_rate', 0)
            emoji = "✅" if rate >= 90 else "⚠️" if rate >= 70 else "❌"
            print(f"{emoji} {category.replace('_', ' ').title()}: {rate:.1f}% ({summary.get('passed', 0)}/{summary.get('total_tests', 0)})")

        # Recommendations
        print("\nRECOMMENDATIONS")
        print("-" * 40)

        if report['overall_success_rate'] >= 95:
            print("🎉 Excellent! System is production-ready.")
        elif report['overall_success_rate'] >= 90:
            print("✨ Good performance. Minor issues should be addressed.")
        elif report['overall_success_rate'] >= 80:
            print("⚡ Acceptable for development. Address failed tests before production.")
        else:
            print("🔧 Significant issues detected. Review failed tests and fix critical problems.")

        # Failed test summary
        failed_categories = [cat for cat, summary in report['test_summaries'].items()
                           if summary.get('failed', 0) > 0]
        if failed_categories:
            print(f"\nFAILED TEST CATEGORIES: {', '.join(failed_categories)}")

        print("\nDetailed report saved to: complete_uat_report.json")
        print("=" * 60)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Complete UAT for Multi-Document RAG System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--skip-api',
        action='store_true',
        help='Skip API endpoint testing'
    )

    parser.add_argument(
        '--skip-pdf',
        action='store_true',
        help='Skip real PDF workflow testing'
    )

    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick test suite (reduced test cases)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()

async def main():
    """Main UAT orchestration function"""
    args = parse_arguments()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    orchestrator = UATOrchestrator(args)

    try:
        report = await orchestrator.run_complete_uat_suite()

        if report:
            success = report['overall_success_rate'] >= 80  # 80% minimum threshold
            return 0 if success else 1
        else:
            return 1

    except Exception as e:
        print(f"Fatal error during UAT: {e}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  UAT interrupted by user")
        sys.exit(1)
