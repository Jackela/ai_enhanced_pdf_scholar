"""
Test Helper Utilities for E2E Testing

Common utilities and helpers for end-to-end tests.
"""

import time
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import random
import string
from contextlib import contextmanager
from playwright.sync_api import Page, Response, Request


class TestDataManager:
    """Manage test data lifecycle and cleanup."""

    def __init__(self):
        self.created_resources = {
            'documents': [],
            'users': [],
            'queries': [],
            'files': []
        }

    def track_resource(self, resource_type: str, resource_id: Any):
        """Track a resource for cleanup."""
        if resource_type in self.created_resources:
            self.created_resources[resource_type].append(resource_id)

    def cleanup(self, api_client):
        """Clean up all tracked resources."""
        # Delete documents
        for doc_id in self.created_resources['documents']:
            try:
                api_client.delete(f'/api/documents/{doc_id}')
            except:
                pass

        # Delete users
        for user_id in self.created_resources['users']:
            try:
                api_client.delete(f'/api/users/{user_id}')
            except:
                pass

        # Delete files
        for file_path in self.created_resources['files']:
            try:
                Path(file_path).unlink()
            except:
                pass

        # Clear tracking
        for key in self.created_resources:
            self.created_resources[key] = []


class NetworkMonitor:
    """Monitor network activity during tests."""

    def __init__(self, page: Page):
        self.page = page
        self.requests = []
        self.responses = []
        self.failed_requests = []

        # Set up listeners
        page.on('request', self._on_request)
        page.on('response', self._on_response)
        page.on('requestfailed', self._on_request_failed)

    def _on_request(self, request: Request):
        """Handle request event."""
        self.requests.append({
            'url': request.url,
            'method': request.method,
            'headers': request.headers,
            'timestamp': time.time()
        })

    def _on_response(self, response: Response):
        """Handle response event."""
        self.responses.append({
            'url': response.url,
            'status': response.status,
            'headers': response.headers,
            'timestamp': time.time()
        })

    def _on_request_failed(self, request: Request):
        """Handle failed request."""
        self.failed_requests.append({
            'url': request.url,
            'method': request.method,
            'failure': request.failure,
            'timestamp': time.time()
        })

    def get_api_calls(self, pattern: str = '/api/') -> List[Dict[str, Any]]:
        """Get all API calls matching pattern."""
        return [
            req for req in self.requests
            if pattern in req['url']
        ]

    def get_failed_requests(self) -> List[Dict[str, Any]]:
        """Get all failed requests."""
        return self.failed_requests

    def get_slow_requests(self, threshold: float = 2.0) -> List[Dict[str, Any]]:
        """Get requests that took longer than threshold."""
        slow_requests = []

        for request in self.requests:
            # Find matching response
            response = next(
                (r for r in self.responses if r['url'] == request['url']
                 and r['timestamp'] > request['timestamp']),
                None
            )

            if response:
                duration = response['timestamp'] - request['timestamp']
                if duration > threshold:
                    slow_requests.append({
                        'url': request['url'],
                        'method': request['method'],
                        'duration': duration
                    })

        return slow_requests

    def get_statistics(self) -> Dict[str, Any]:
        """Get network statistics."""
        return {
            'total_requests': len(self.requests),
            'total_responses': len(self.responses),
            'failed_requests': len(self.failed_requests),
            'api_calls': len(self.get_api_calls()),
            'slow_requests': len(self.get_slow_requests()),
            'unique_endpoints': len(set(req['url'] for req in self.requests))
        }


class VisualRegression:
    """Visual regression testing utilities."""

    def __init__(self, baseline_dir: Path = Path("tests_e2e/visual_baselines")):
        self.baseline_dir = baseline_dir
        self.baseline_dir.mkdir(exist_ok=True)

    def capture_screenshot(self, page: Page, name: str) -> Path:
        """Capture a screenshot for comparison."""
        screenshot_path = self.baseline_dir / f"{name}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        return screenshot_path

    def compare_screenshots(self, current: Path, baseline: Path, threshold: float = 0.1) -> bool:
        """
        Compare two screenshots for visual differences.
        Returns True if similar within threshold.
        """
        try:
            from PIL import Image
            import numpy as np

            # Load images
            img1 = Image.open(current)
            img2 = Image.open(baseline)

            # Resize if needed
            if img1.size != img2.size:
                img2 = img2.resize(img1.size)

            # Convert to arrays
            arr1 = np.array(img1)
            arr2 = np.array(img2)

            # Calculate difference
            diff = np.abs(arr1.astype(float) - arr2.astype(float))
            max_diff = np.max(diff) / 255.0

            return max_diff <= threshold

        except ImportError:
            # PIL not available, use simple hash comparison
            hash1 = hashlib.md5(current.read_bytes()).hexdigest()
            hash2 = hashlib.md5(baseline.read_bytes()).hexdigest()
            return hash1 == hash2

    def assert_visual_match(self, page: Page, name: str, update_baseline: bool = False):
        """Assert that current page matches visual baseline."""
        current = self.capture_screenshot(page, f"{name}_current")
        baseline = self.baseline_dir / f"{name}_baseline.png"

        if update_baseline or not baseline.exists():
            # Create/update baseline
            current.rename(baseline)
            return True

        # Compare with baseline
        matches = self.compare_screenshots(current, baseline)

        if not matches:
            # Save diff for debugging
            diff_path = self.baseline_dir / f"{name}_diff.png"
            current.rename(diff_path)
            raise AssertionError(f"Visual regression detected for {name}. Check {diff_path}")

        # Clean up current screenshot
        current.unlink()
        return True


class PerformanceProfiler:
    """Profile performance during tests."""

    def __init__(self):
        self.metrics = []
        self.current_operation = None
        self.start_time = None

    @contextmanager
    def measure(self, operation: str):
        """Context manager to measure operation time."""
        self.current_operation = operation
        self.start_time = time.time()

        try:
            yield self
        finally:
            duration = time.time() - self.start_time
            self.metrics.append({
                'operation': operation,
                'duration': duration,
                'timestamp': datetime.now().isoformat()
            })
            self.current_operation = None
            self.start_time = None

    def get_report(self) -> Dict[str, Any]:
        """Generate performance report."""
        if not self.metrics:
            return {}

        durations = [m['duration'] for m in self.metrics]
        operations = {}

        for metric in self.metrics:
            op = metric['operation']
            if op not in operations:
                operations[op] = []
            operations[op].append(metric['duration'])

        return {
            'total_operations': len(self.metrics),
            'total_time': sum(durations),
            'average_time': sum(durations) / len(durations),
            'slowest_operation': max(self.metrics, key=lambda x: x['duration']),
            'operations_summary': {
                op: {
                    'count': len(times),
                    'total': sum(times),
                    'average': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times)
                }
                for op, times in operations.items()
            }
        }


class TestReporter:
    """Generate test reports."""

    def __init__(self, output_dir: Path = Path("tests_e2e/reports")):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.test_results = []

    def add_test_result(
        self,
        test_name: str,
        status: str,
        duration: float,
        details: Dict[str, Any] = None
    ):
        """Add a test result."""
        self.test_results.append({
            'test_name': test_name,
            'status': status,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        })

    def generate_html_report(self) -> Path:
        """Generate HTML test report."""
        report_path = self.output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>E2E Test Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                .summary { background: #f0f0f0; padding: 15px; margin: 20px 0; }
                .passed { color: green; }
                .failed { color: red; }
                .skipped { color: orange; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 10px; text-align: left; border: 1px solid #ddd; }
                th { background: #4CAF50; color: white; }
                tr:nth-child(even) { background: #f2f2f2; }
            </style>
        </head>
        <body>
            <h1>E2E Test Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p>Total Tests: {total}</p>
                <p class="passed">Passed: {passed}</p>
                <p class="failed">Failed: {failed}</p>
                <p class="skipped">Skipped: {skipped}</p>
                <p>Total Duration: {duration:.2f}s</p>
            </div>
            <h2>Test Results</h2>
            <table>
                <tr>
                    <th>Test Name</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Timestamp</th>
                </tr>
                {test_rows}
            </table>
        </body>
        </html>
        """

        # Calculate summary
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['status'] == 'passed')
        failed = sum(1 for r in self.test_results if r['status'] == 'failed')
        skipped = sum(1 for r in self.test_results if r['status'] == 'skipped')
        total_duration = sum(r['duration'] for r in self.test_results)

        # Generate test rows
        test_rows = ""
        for result in self.test_results:
            status_class = result['status']
            test_rows += f"""
            <tr>
                <td>{result['test_name']}</td>
                <td class="{status_class}">{result['status'].upper()}</td>
                <td>{result['duration']:.2f}s</td>
                <td>{result['timestamp']}</td>
            </tr>
            """

        # Format HTML
        html = html_content.format(
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration=total_duration,
            test_rows=test_rows
        )

        report_path.write_text(html)
        return report_path

    def generate_json_report(self) -> Path:
        """Generate JSON test report."""
        report_path = self.output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': len(self.test_results),
                'passed': sum(1 for r in self.test_results if r['status'] == 'passed'),
                'failed': sum(1 for r in self.test_results if r['status'] == 'failed'),
                'skipped': sum(1 for r in self.test_results if r['status'] == 'skipped'),
                'duration': sum(r['duration'] for r in self.test_results)
            },
            'tests': self.test_results
        }

        report_path.write_text(json.dumps(report_data, indent=2))
        return report_path


class WaitHelper:
    """Helper for waiting conditions."""

    @staticmethod
    def wait_for_condition(
        condition: Callable[[], bool],
        timeout: float = 10,
        interval: float = 0.5,
        message: str = "Condition not met"
    ) -> bool:
        """Wait for a condition to become true."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if condition():
                return True
            time.sleep(interval)

        raise TimeoutError(f"{message} after {timeout} seconds")

    @staticmethod
    def wait_for_text_change(
        page: Page,
        selector: str,
        initial_text: str,
        timeout: float = 10
    ) -> str:
        """Wait for text in element to change."""
        def text_changed():
            current = page.locator(selector).text_content()
            return current != initial_text

        WaitHelper.wait_for_condition(
            text_changed,
            timeout,
            message=f"Text in {selector} did not change"
        )

        return page.locator(selector).text_content()

    @staticmethod
    def wait_for_element_count(
        page: Page,
        selector: str,
        expected_count: int,
        timeout: float = 10
    ):
        """Wait for specific number of elements."""
        def count_matches():
            return page.locator(selector).count() == expected_count

        WaitHelper.wait_for_condition(
            count_matches,
            timeout,
            message=f"Element count for {selector} did not reach {expected_count}"
        )