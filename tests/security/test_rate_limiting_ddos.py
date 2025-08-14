"""
Comprehensive Rate Limiting and DDoS Protection Tests
Tests for rate limiting, throttling, and DDoS mitigation mechanisms.
"""

import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Tuple
import pytest
from unittest.mock import Mock, patch
from fastapi import status
from fastapi.testclient import TestClient
import statistics

from tests.security.enhanced_security_utils import (
    SecurityMonitor, AsyncSecurityTester, SecurityTestResult,
    AttackVector, SecuritySeverity
)


class TestRateLimiting:
    """Test rate limiting implementation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def monitor(self):
        """Create security monitor."""
        return SecurityMonitor()

    def test_basic_rate_limiting(self, client, monitor):
        """Test basic rate limiting functionality."""
        endpoint = "/api/documents/search"
        rate_limit = 10  # Expected rate limit per minute

        responses = []
        start_time = time.time()

        # Make requests until rate limited
        for i in range(rate_limit + 5):
            response = client.get(endpoint, params={"q": f"test_{i}"})
            responses.append({
                "status": response.status_code,
                "time": time.time() - start_time,
                "headers": dict(response.headers)
            })

            # Check for rate limit headers
            if "X-RateLimit-Limit" in response.headers:
                assert int(response.headers["X-RateLimit-Limit"]) == rate_limit

            if response.status_code == 429:
                # Rate limited
                monitor.log_event("rate_limit_triggered", {
                    "endpoint": endpoint,
                    "request_count": i + 1,
                    "time_elapsed": time.time() - start_time
                })
                break

        # Verify rate limiting kicked in
        rate_limited = any(r["status"] == 429 for r in responses)
        assert rate_limited, "Rate limiting not triggered"

        # Check retry-after header
        limited_response = next((r for r in responses if r["status"] == 429), None)
        if limited_response and "Retry-After" in limited_response["headers"]:
            retry_after = int(limited_response["headers"]["Retry-After"])
            assert retry_after > 0, "Invalid Retry-After header"

    def test_per_endpoint_rate_limits(self, client):
        """Test different rate limits for different endpoints."""
        endpoints_config = [
            ("/api/auth/login", 5),       # Strict limit for auth
            ("/api/search", 30),           # Moderate limit for search
            ("/api/static/image.png", 100), # High limit for static
        ]

        for endpoint, expected_limit in endpoints_config:
            responses = []

            # Make requests up to and beyond limit
            for i in range(expected_limit + 5):
                response = client.get(endpoint)
                responses.append(response.status_code)

                if response.status_code == 429:
                    break

            # Count successful requests before rate limiting
            successful = sum(1 for status in responses if status in [200, 404])

            # Should allow approximately the expected limit
            assert successful <= expected_limit + 2, \
                   f"Rate limit not enforced for {endpoint}"

    def test_user_based_rate_limiting(self, client):
        """Test rate limiting per user/API key."""
        # Test with different user tokens
        users = [
            {"Authorization": "Bearer user1_token"},
            {"Authorization": "Bearer user2_token"},
            {"Authorization": "Bearer user3_token"},
        ]

        results = {}

        for headers in users:
            responses = []

            # Each user should have independent rate limit
            for i in range(15):
                response = client.get("/api/data", headers=headers)
                responses.append(response.status_code)

                if response.status_code == 429:
                    break

            results[headers["Authorization"]] = responses

        # Each user should hit their own rate limit independently
        for user, responses in results.items():
            successful = sum(1 for status in responses if status == 200)
            assert successful > 0, f"No successful requests for {user}"

    def test_ip_based_rate_limiting(self, client):
        """Test rate limiting based on IP address."""
        # Simulate requests from different IPs
        ips = ["192.168.1.1", "192.168.1.2", "10.0.0.1"]

        for ip in ips:
            with patch.object(client, 'headers', {"X-Forwarded-For": ip}):
                responses = []

                for i in range(20):
                    response = client.get("/api/search", params={"q": f"test_{i}"})
                    responses.append(response.status_code)

                    if response.status_code == 429:
                        break

                # Each IP should have independent rate limit
                successful = sum(1 for status in responses if status == 200)
                assert successful > 0, f"No successful requests from IP {ip}"

    def test_sliding_window_rate_limiting(self, client):
        """Test sliding window rate limiting algorithm."""
        endpoint = "/api/expensive-operation"
        window_size = 60  # 60 seconds window
        max_requests = 10

        # Make initial burst of requests
        for i in range(max_requests):
            response = client.post(endpoint, json={"data": f"test_{i}"})
            assert response.status_code != 429, f"Premature rate limiting at request {i+1}"

        # Next request should be rate limited
        response = client.post(endpoint, json={"data": "test_extra"})
        assert response.status_code == 429, "Rate limit not enforced"

        # Wait for partial window to slide
        time.sleep(window_size / 2)

        # Should allow some requests as window slides
        allowed = 0
        for i in range(5):
            response = client.post(endpoint, json={"data": f"test_slide_{i}"})
            if response.status_code != 429:
                allowed += 1

        assert allowed > 0, "Sliding window not working"

    def test_token_bucket_rate_limiting(self, client):
        """Test token bucket rate limiting algorithm."""
        endpoint = "/api/token-bucket-endpoint"
        bucket_size = 10
        refill_rate = 2  # tokens per second

        # Exhaust bucket
        for i in range(bucket_size):
            response = client.get(endpoint)
            assert response.status_code != 429

        # Should be rate limited
        response = client.get(endpoint)
        assert response.status_code == 429

        # Wait for tokens to refill
        time.sleep(2)  # Should get ~4 tokens

        # Should allow some requests
        allowed = 0
        for i in range(5):
            response = client.get(endpoint)
            if response.status_code != 429:
                allowed += 1

        assert allowed >= 3, "Token bucket not refilling properly"

    def test_distributed_rate_limiting(self, client):
        """Test rate limiting across distributed system."""
        # Simulate multiple application instances
        instances = []
        for i in range(3):
            instance_client = TestClient(client.app)
            instances.append(instance_client)

        total_requests = []

        # Make concurrent requests from all instances
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []

            for instance in instances:
                for i in range(10):
                    future = executor.submit(
                        instance.get, "/api/shared-limit", {"q": f"test_{i}"}
                    )
                    futures.append(future)

            for future in as_completed(futures):
                response = future.result()
                total_requests.append(response.status_code)

        # Should enforce global rate limit across instances
        rate_limited = sum(1 for status in total_requests if status == 429)
        assert rate_limited > 0, "Distributed rate limiting not working"


class TestDDoSProtection:
    """Test DDoS protection mechanisms."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def async_tester(self, client):
        """Create async security tester."""
        return AsyncSecurityTester()

    def test_connection_throttling(self, client):
        """Test connection throttling under load."""
        connections = []
        max_connections = 100

        def create_connection(i):
            try:
                response = client.get(f"/api/test?id={i}")
                return response.status_code
            except:
                return 503

        # Attempt to create many concurrent connections
        with ThreadPoolExecutor(max_workers=max_connections) as executor:
            futures = [executor.submit(create_connection, i)
                      for i in range(max_connections)]

            for future in as_completed(futures):
                connections.append(future.result())

        # Should throttle excessive connections
        throttled = sum(1 for status in connections if status in [429, 503])
        assert throttled > 0, "Connection throttling not working"

    def test_request_size_limits(self, client):
        """Test request size limits to prevent large payload attacks."""
        # Test various payload sizes
        payload_sizes = [
            1024,        # 1 KB - should pass
            1024 * 100,  # 100 KB - should pass
            1024 * 1024, # 1 MB - might pass
            1024 * 1024 * 10,  # 10 MB - should fail
            1024 * 1024 * 100, # 100 MB - should definitely fail
        ]

        for size in payload_sizes:
            data = "A" * size
            response = client.post(
                "/api/upload/text",
                json={"content": data}
            )

            # Large payloads should be rejected
            if size > 1024 * 1024 * 5:  # > 5MB
                assert response.status_code in [413, 400], \
                       f"Large payload ({size} bytes) not rejected"

    def test_slowloris_protection(self, client):
        """Test protection against Slowloris attacks."""
        import socket
        import time

        # Try to create slow connections
        slow_connections = []

        for i in range(5):
            try:
                # Create socket but send data very slowly
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)

                # Assuming test server is on localhost:8000
                # This is a simulation - adjust for actual test environment
                sock.connect(("localhost", 8000))

                # Send partial HTTP request slowly
                sock.send(b"GET /api/test HTTP/1.1\r\n")
                time.sleep(1)
                sock.send(b"Host: localhost\r\n")
                time.sleep(1)

                slow_connections.append(sock)
            except:
                pass

        # Server should timeout slow connections
        time.sleep(10)

        # Try normal request - should still work
        response = client.get("/api/health")
        assert response.status_code == 200, "Server blocked after slow connections"

        # Clean up
        for sock in slow_connections:
            try:
                sock.close()
            except:
                pass

    def test_syn_flood_protection(self, client):
        """Test SYN flood protection (simulated)."""
        # Simulate many connection attempts
        connection_attempts = []

        def attempt_connection(i):
            try:
                # Simulate SYN packet (connection attempt)
                response = client.get("/api/connect", timeout=0.1)
                return "connected"
            except:
                return "timeout"

        # Attempt many concurrent connections
        with ThreadPoolExecutor(max_workers=200) as executor:
            futures = [executor.submit(attempt_connection, i)
                      for i in range(200)]

            for future in as_completed(futures):
                connection_attempts.append(future.result())

        # Should limit concurrent SYN connections
        timeouts = sum(1 for result in connection_attempts if result == "timeout")
        assert timeouts > 0, "SYN flood protection not working"

    def test_amplification_attack_prevention(self, client):
        """Test prevention of amplification attacks."""
        # Test that responses aren't significantly larger than requests
        small_request = {"query": "a"}

        response = client.post("/api/search", json=small_request)

        if response.status_code == 200:
            request_size = len(str(small_request))
            response_size = len(response.text)

            # Response shouldn't be drastically larger (amplification factor)
            amplification_factor = response_size / request_size
            assert amplification_factor < 100, \
                   f"High amplification factor: {amplification_factor}"

    def test_recursive_request_protection(self, client):
        """Test protection against recursive/nested requests."""
        # Try to create recursive structure
        recursive_data = {"data": {}}
        current = recursive_data["data"]

        # Create deep nesting
        for i in range(1000):
            current["nested"] = {}
            current = current["nested"]

        response = client.post("/api/process", json=recursive_data)

        # Should reject or handle deep recursion
        assert response.status_code in [400, 413, 422], \
               "Deep recursion not prevented"


class TestBruteForceProtection:
    """Test brute force attack protection."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    def test_login_brute_force_protection(self, client):
        """Test protection against login brute force attacks."""
        username = "testuser"
        attempts = []

        # Try multiple login attempts with wrong passwords
        for i in range(10):
            response = client.post(
                "/api/auth/login",
                json={
                    "username": username,
                    "password": f"wrong_password_{i}"
                }
            )
            attempts.append({
                "attempt": i + 1,
                "status": response.status_code,
                "time": time.time()
            })

            # Should start blocking after threshold
            if i > 5 and response.status_code == 429:
                break

        # Should implement progressive delays or blocking
        blocked = any(a["status"] == 429 for a in attempts)
        assert blocked, "Brute force protection not triggered"

    def test_password_reset_brute_force(self, client):
        """Test protection against password reset brute force."""
        email = "test@example.com"

        # Try multiple password reset requests
        for i in range(10):
            response = client.post(
                "/api/auth/reset-password",
                json={"email": email}
            )

            # Should rate limit password reset attempts
            if i > 3 and response.status_code == 429:
                assert True
                return

        assert False, "Password reset not rate limited"

    def test_api_key_brute_force(self, client):
        """Test protection against API key brute force."""
        attempts = []

        # Try multiple API requests with invalid keys
        for i in range(20):
            response = client.get(
                "/api/protected",
                headers={"X-API-Key": f"invalid_key_{i}"}
            )
            attempts.append(response.status_code)

            # Should block after threshold
            if response.status_code == 429:
                break

        # Should implement API key brute force protection
        assert 429 in attempts, "API key brute force not protected"

    def test_captcha_enforcement(self, client):
        """Test CAPTCHA enforcement after failed attempts."""
        # Make several failed login attempts
        for i in range(5):
            client.post(
                "/api/auth/login",
                json={
                    "username": "user",
                    "password": f"wrong_{i}"
                }
            )

        # Next attempt should require CAPTCHA
        response = client.post(
            "/api/auth/login",
            json={
                "username": "user",
                "password": "correct_password"
            }
        )

        # Should require CAPTCHA validation
        if response.status_code == 400:
            error = response.json()
            assert "captcha" in str(error).lower(), \
                   "CAPTCHA not required after failed attempts"


class TestResourceExhaustionPrevention:
    """Test prevention of resource exhaustion attacks."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    def test_cpu_exhaustion_prevention(self, client):
        """Test prevention of CPU exhaustion attacks."""
        # Try to trigger CPU-intensive operations
        cpu_intensive_payloads = [
            {"regex": "(a+)+" + "a" * 100},  # ReDoS
            {"hash_iterations": 1000000},     # Excessive hashing
            {"factorial": 10000},              # Large computation
        ]

        for payload in cpu_intensive_payloads:
            start_time = time.time()
            response = client.post("/api/compute", json=payload)
            elapsed = time.time() - start_time

            # Should timeout or reject expensive operations
            assert elapsed < 5.0, f"CPU exhaustion not prevented: {elapsed}s"
            assert response.status_code in [400, 408, 503]

    def test_memory_exhaustion_prevention(self, client):
        """Test prevention of memory exhaustion attacks."""
        # Try to consume excessive memory
        memory_payloads = [
            {"array_size": 10**9},  # Huge array
            {"string_length": 10**9},  # Huge string
            {"cache_items": 10**6},  # Cache pollution
        ]

        for payload in memory_payloads:
            response = client.post("/api/allocate", json=payload)

            # Should reject excessive memory allocation
            assert response.status_code in [400, 413, 507], \
                   "Memory exhaustion not prevented"

    def test_disk_exhaustion_prevention(self, client):
        """Test prevention of disk exhaustion attacks."""
        # Try to fill disk with uploads
        large_file = b"A" * (100 * 1024 * 1024)  # 100MB

        files = [("file", ("large.txt", large_file, "text/plain"))]
        response = client.post("/api/upload", files=files)

        # Should reject files that are too large
        assert response.status_code in [413, 507], \
               "Disk exhaustion not prevented"

    def test_connection_pool_exhaustion(self, client):
        """Test prevention of connection pool exhaustion."""
        connections = []

        # Try to exhaust connection pool
        def hold_connection(i):
            try:
                # Create connection and hold it
                response = client.get(f"/api/long-poll?id={i}", timeout=30)
                return response.status_code
            except:
                return 503

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(hold_connection, i)
                      for i in range(100)]

            for future in as_completed(futures):
                connections.append(future.result())

        # Should limit concurrent connections
        rejected = sum(1 for status in connections if status in [429, 503])
        assert rejected > 0, "Connection pool exhaustion not prevented"


class TestRateLimitingBypass:
    """Test common rate limiting bypass techniques."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    def test_header_spoofing_bypass(self, client):
        """Test that header spoofing doesn't bypass rate limits."""
        # Try to bypass with different headers
        bypass_headers = [
            {"X-Forwarded-For": "1.2.3.4"},
            {"X-Real-IP": "5.6.7.8"},
            {"X-Originating-IP": "9.10.11.12"},
            {"CF-Connecting-IP": "13.14.15.16"},
        ]

        for headers in bypass_headers:
            # Exhaust rate limit
            for i in range(20):
                response = client.get("/api/limited", headers=headers)
                if response.status_code == 429:
                    break

            # Should still be rate limited despite header changes
            assert response.status_code == 429, \
                   f"Rate limit bypassed with headers: {headers}"

    def test_case_variation_bypass(self, client):
        """Test that case variations don't bypass rate limits."""
        # Try different case variations of same endpoint
        endpoints = [
            "/api/search",
            "/Api/Search",
            "/API/SEARCH",
            "/ApI/SeArCh",
        ]

        total_requests = 0

        for endpoint in endpoints:
            for i in range(10):
                response = client.get(endpoint, params={"q": "test"})
                total_requests += 1

                if response.status_code == 429:
                    # Rate limit should apply across case variations
                    assert total_requests < len(endpoints) * 10, \
                           "Rate limit bypassed with case variations"
                    return

        assert False, "Rate limiting not applied to case variations"

    def test_encoding_bypass(self, client):
        """Test that URL encoding doesn't bypass rate limits."""
        # Try encoded versions of endpoint
        encoded_endpoints = [
            "/api/search",
            "/api%2Fsearch",
            "/api%2fsearch",
            "/%61%70%69/search",  # 'api' in hex
        ]

        for endpoint in encoded_endpoints:
            for i in range(15):
                response = client.get(endpoint)
                if response.status_code == 429:
                    break

            # Should maintain rate limit despite encoding
            assert response.status_code == 429, \
                   f"Rate limit bypassed with encoding: {endpoint}"


class TestRateLimitingMetrics:
    """Test rate limiting metrics and monitoring."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def monitor(self):
        """Create security monitor."""
        return SecurityMonitor()

    def test_rate_limit_metrics_collection(self, client, monitor):
        """Test collection of rate limiting metrics."""
        endpoint = "/api/test"
        metrics = {
            "total_requests": 0,
            "rate_limited": 0,
            "response_times": [],
            "rate_limit_headers": []
        }

        # Make requests and collect metrics
        for i in range(30):
            start_time = time.time()
            response = client.get(endpoint)
            elapsed = time.time() - start_time

            metrics["total_requests"] += 1
            metrics["response_times"].append(elapsed)

            if response.status_code == 429:
                metrics["rate_limited"] += 1
                monitor.log_event("rate_limit_hit", {
                    "endpoint": endpoint,
                    "request_number": i + 1
                })

            # Collect rate limit headers
            if "X-RateLimit-Remaining" in response.headers:
                metrics["rate_limit_headers"].append({
                    "remaining": response.headers["X-RateLimit-Remaining"],
                    "limit": response.headers.get("X-RateLimit-Limit"),
                    "reset": response.headers.get("X-RateLimit-Reset")
                })

        # Analyze metrics
        assert metrics["rate_limited"] > 0, "No rate limiting occurred"
        assert len(metrics["rate_limit_headers"]) > 0, "No rate limit headers"

        # Check response time doesn't degrade under rate limiting
        avg_response_time = statistics.mean(metrics["response_times"])
        assert avg_response_time < 1.0, f"High response time: {avg_response_time}s"

        return metrics

    def test_rate_limit_effectiveness(self, client):
        """Test effectiveness of rate limiting."""
        # Measure request rate with and without rate limiting

        # First, make requests normally
        normal_start = time.time()
        normal_responses = []

        for i in range(20):
            response = client.get("/api/unlimited")  # Hypothetical unlimited endpoint
            normal_responses.append(response.status_code)

        normal_duration = time.time() - normal_start
        normal_rate = len(normal_responses) / normal_duration

        # Now with rate limited endpoint
        limited_start = time.time()
        limited_responses = []

        for i in range(20):
            response = client.get("/api/limited")
            limited_responses.append(response.status_code)

            # If rate limited, wait
            if response.status_code == 429:
                time.sleep(1)

        limited_duration = time.time() - limited_start
        limited_rate = len([r for r in limited_responses if r != 429]) / limited_duration

        # Rate should be effectively limited
        assert limited_rate < normal_rate, \
               "Rate limiting not effectively reducing request rate"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])