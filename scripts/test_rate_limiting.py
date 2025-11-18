"""
Rate Limiting Performance and Load Testing Script
Tests rate limiting under high load conditions
"""

import argparse
import asyncio
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import aiohttp

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class TestResult:
    """Result of a rate limiting test."""

    endpoint: str
    total_requests: int
    success_requests: int
    rate_limited_requests: int
    error_requests: int
    avg_response_time: float
    max_response_time: float
    min_response_time: float
    requests_per_second: float


class RateLimitTester:
    """Rate limiting performance tester."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: aiohttp.ClientSession = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "rate-limit-tester"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def make_request(
        self,
        endpoint: str,
        method: str = "GET",
        client_ip: str = None,
        data: dict = None,
    ) -> tuple[int, float]:
        """Make a single request and return (status_code, response_time)."""
        headers = {}
        if client_ip:
            headers["X-Forwarded-For"] = client_ip

        start_time = time.time()
        try:
            if method.upper() == "GET":
                async with self.session.get(
                    f"{self.base_url}{endpoint}", headers=headers
                ) as response:
                    await response.text()  # Read response body
                    return response.status, time.time() - start_time
            elif method.upper() == "POST":
                async with self.session.post(
                    f"{self.base_url}{endpoint}", headers=headers, json=data
                ) as response:
                    await response.text()
                    return response.status, time.time() - start_time
        except Exception:
            return 0, time.time() - start_time  # Error status

    async def burst_test(
        self,
        endpoint: str,
        num_requests: int,
        client_ip: str = "192.168.1.100",
        method: str = "GET",
        data: dict = None,
    ) -> TestResult:
        """Test burst requests to an endpoint."""
        print(f"Testing {num_requests} burst requests to {endpoint}...")

        tasks = []
        start_time = time.time()

        # Create all requests simultaneously
        for i in range(num_requests):
            task = self.make_request(endpoint, method, f"{client_ip}{i % 10}", data)
            tasks.append(task)

        # Execute all requests
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Analyze results
        status_codes = [r[0] for r in results]
        response_times = [r[1] for r in results]

        success_count = sum(1 for code in status_codes if code == 200)
        rate_limited_count = sum(1 for code in status_codes if code == 429)
        error_count = sum(1 for code in status_codes if code not in [200, 429])

        return TestResult(
            endpoint=endpoint,
            total_requests=num_requests,
            success_requests=success_count,
            rate_limited_requests=rate_limited_count,
            error_requests=error_count,
            avg_response_time=statistics.mean(response_times),
            max_response_time=max(response_times),
            min_response_time=min(response_times),
            requests_per_second=num_requests / total_time if total_time > 0 else 0,
        )

    async def sustained_load_test(
        self,
        endpoint: str,
        requests_per_second: int,
        duration_seconds: int,
        client_ip: str = "192.168.1.200",
    ) -> TestResult:
        """Test sustained load over time."""
        print(
            f"Testing sustained load: {requests_per_second} RPS for {duration_seconds}s on {endpoint}..."
        )

        interval = 1.0 / requests_per_second
        total_requests = requests_per_second * duration_seconds

        results = []
        start_time = time.time()

        for i in range(total_requests):
            # Maintain consistent rate
            expected_time = start_time + (i * interval)
            current_time = time.time()
            if expected_time > current_time:
                await asyncio.sleep(expected_time - current_time)

            # Make request
            status, response_time = await self.make_request(
                endpoint, client_ip=f"{client_ip}{i % 5}"
            )
            results.append((status, response_time))

            # Stop if we've exceeded duration
            if time.time() - start_time > duration_seconds:
                break

        total_time = time.time() - start_time

        # Analyze results
        status_codes = [r[0] for r in results]
        response_times = [r[1] for r in results]

        success_count = sum(1 for code in status_codes if code == 200)
        rate_limited_count = sum(1 for code in status_codes if code == 429)
        error_count = sum(1 for code in status_codes if code not in [200, 429])

        return TestResult(
            endpoint=endpoint,
            total_requests=len(results),
            success_requests=success_count,
            rate_limited_requests=rate_limited_count,
            error_requests=error_count,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            requests_per_second=len(results) / total_time if total_time > 0 else 0,
        )

    async def multi_ip_test(
        self, endpoint: str, num_ips: int, requests_per_ip: int
    ) -> TestResult:
        """Test multiple IPs to verify separate rate limiting."""
        print(
            f"Testing {num_ips} IPs with {requests_per_ip} requests each on {endpoint}..."
        )

        tasks = []
        start_time = time.time()

        # Create requests from different IPs
        for ip_idx in range(num_ips):
            client_ip = f"192.168.{ip_idx // 256}.{ip_idx % 256}"
            for req_idx in range(requests_per_ip):
                task = self.make_request(endpoint, client_ip=client_ip)
                tasks.append(task)

        # Execute all requests
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Analyze results
        status_codes = [r[0] for r in results]
        response_times = [r[1] for r in results]

        success_count = sum(1 for code in status_codes if code == 200)
        rate_limited_count = sum(1 for code in status_codes if code == 429)
        error_count = sum(1 for code in status_codes if code not in [200, 429])

        total_requests = num_ips * requests_per_ip

        return TestResult(
            endpoint=endpoint,
            total_requests=total_requests,
            success_requests=success_count,
            rate_limited_requests=rate_limited_count,
            error_requests=error_count,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            requests_per_second=total_requests / total_time if total_time > 0 else 0,
        )

    async def test_endpoint_specific_limits(self) -> dict[str, TestResult]:
        """Test different endpoints to verify specific rate limits."""
        endpoints = [
            ("/api/system/health", "GET", None),
            ("/api/documents", "GET", None),
            ("/api/rag/query", "POST", {"query": "test"}),
        ]

        results = {}

        for endpoint, method, data in endpoints:
            print(f"\nTesting endpoint-specific limits for {endpoint}...")

            # Test with high burst to trigger rate limiting
            result = await self.burst_test(endpoint, 50, method=method, data=data)
            results[endpoint] = result

            # Wait between tests to avoid interference
            await asyncio.sleep(2)

        return results


def print_results(result: TestResult):
    """Print test results in a readable format."""
    print(f"\n{'='*60}")
    print(f"Results for {result.endpoint}")
    print(f"{'='*60}")
    print(f"Total Requests:       {result.total_requests}")
    print(
        f"Successful (200):     {result.success_requests} ({result.success_requests/result.total_requests*100:.1f}%)"
    )
    print(
        f"Rate Limited (429):   {result.rate_limited_requests} ({result.rate_limited_requests/result.total_requests*100:.1f}%)"
    )
    print(
        f"Errors:               {result.error_requests} ({result.error_requests/result.total_requests*100:.1f}%)"
    )
    print(f"Avg Response Time:    {result.avg_response_time*1000:.1f}ms")
    print(f"Min Response Time:    {result.min_response_time*1000:.1f}ms")
    print(f"Max Response Time:    {result.max_response_time*1000:.1f}ms")
    print(f"Throughput:           {result.requests_per_second:.1f} requests/sec")

    # Rate limiting effectiveness
    expected_rate_limited = max(
        0, result.total_requests - 60
    )  # Assuming 60 req/min default
    if expected_rate_limited > 0:
        effectiveness = result.rate_limited_requests / expected_rate_limited * 100
        print(f"Rate Limit Effectiveness: {effectiveness:.1f}%")


async def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Rate Limiting Performance Tests")
    parser.add_argument(
        "--url", default="http://localhost:8000", help="Base URL for API"
    )
    parser.add_argument(
        "--test",
        choices=["burst", "sustained", "multi-ip", "endpoints", "all"],
        default="all",
        help="Type of test to run",
    )
    parser.add_argument(
        "--requests", type=int, default=100, help="Number of requests for burst test"
    )
    parser.add_argument(
        "--rps", type=int, default=10, help="Requests per second for sustained test"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration in seconds for sustained test",
    )
    parser.add_argument(
        "--ips", type=int, default=10, help="Number of IPs for multi-IP test"
    )

    args = parser.parse_args()

    print("Starting Rate Limiting Performance Tests...")
    print(f"Target URL: {args.url}")
    print(f"Test Type: {args.test}")

    async with RateLimitTester(args.url) as tester:
        try:
            # Check if API is accessible
            status, _ = await tester.make_request("/api/system/health")
            if status != 200:
                print(f"Warning: API health check returned status {status}")
        except Exception as e:
            print(f"Error: Could not connect to API at {args.url}: {e}")
            return 1

        # Run selected tests
        if args.test in ["burst", "all"]:
            result = await tester.burst_test("/api/documents", args.requests)
            print_results(result)

        if args.test in ["sustained", "all"]:
            result = await tester.sustained_load_test(
                "/api/documents", args.rps, args.duration
            )
            print_results(result)

        if args.test in ["multi-ip", "all"]:
            result = await tester.multi_ip_test("/api/documents", args.ips, 10)
            print_results(result)

        if args.test in ["endpoints", "all"]:
            results = await tester.test_endpoint_specific_limits()
            for endpoint, result in results.items():
                print_results(result)

    print("\nRate limiting tests completed!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
