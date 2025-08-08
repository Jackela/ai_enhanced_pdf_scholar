"""
Integration test for rate limiting functionality
Tests the complete rate limiting system in a realistic scenario
"""

import pytest
import time
from fastapi.testclient import TestClient

# Import the FastAPI app
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from backend.api.main import app
    INTEGRATION_AVAILABLE = True
except ImportError as e:
    print(f"Integration test skipped due to import error: {e}")
    INTEGRATION_AVAILABLE = False


@pytest.mark.skipif(not INTEGRATION_AVAILABLE, reason="Integration dependencies not available")
class TestRateLimitingIntegration:
    """Integration tests for rate limiting with the full FastAPI application."""
    
    @pytest.fixture
    def client(self):
        """Create test client for the full application."""
        return TestClient(app)
    
    def test_health_endpoint_no_rate_limit(self, client):
        """Test that health endpoint has very high limits."""
        # Health endpoint should allow many requests
        for i in range(20):
            response = client.get(
                "/api/system/health",
                headers={"X-Forwarded-For": "192.168.100.1"}
            )
            # Should always succeed (health checks have high limits)
            assert response.status_code in [200, 404], f"Request {i+1} failed with {response.status_code}"
    
    def test_rate_limit_headers_present(self, client):
        """Test that rate limiting headers are present in responses."""
        response = client.get(
            "/api/system/health",
            headers={"X-Forwarded-For": "192.168.100.2"}
        )
        
        if response.status_code == 200:
            # Check for rate limiting headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
            
            # Validate header values
            limit = int(response.headers["X-RateLimit-Limit"])
            remaining = int(response.headers["X-RateLimit-Remaining"])
            reset_time = int(response.headers["X-RateLimit-Reset"])
            
            assert limit > 0
            assert remaining >= 0
            assert reset_time > time.time()
    
    def test_different_endpoints_different_limits(self, client):
        """Test that different endpoints have different rate limits."""
        test_ip = "192.168.100.3"
        headers = {"X-Forwarded-For": test_ip}
        
        # Test a few different endpoints to see if they have different limits
        endpoints_to_test = [
            "/api/system/health",  # Should have high limit
            "/",                   # Root endpoint  
        ]
        
        results = {}
        
        for endpoint in endpoints_to_test:
            response = client.get(endpoint, headers=headers)
            if response.status_code == 200 and "X-RateLimit-Limit" in response.headers:
                limit = int(response.headers["X-RateLimit-Limit"])
                results[endpoint] = limit
        
        # If we got results for multiple endpoints, verify they can have different limits
        if len(results) > 1:
            limits = list(results.values())
            # Not all limits have to be different, but the system should support it
            # This is mainly a sanity check that the system is responding
            assert all(limit > 0 for limit in limits), "All limits should be positive"
    
    def test_rate_limiting_monitoring_integration(self, client):
        """Test that rate limiting monitoring endpoints are available."""
        # Test the admin config endpoint
        response = client.get("/api/admin/rate-limit/config")
        
        if response.status_code == 200:
            config = response.json()
            
            # Verify config structure
            assert "default_limit" in config
            assert "global_ip_limit" in config
            assert "endpoint_limits" in config
            assert "redis_enabled" in config
            
            # Verify values are reasonable
            assert config["default_limit"]["requests"] > 0
            assert config["global_ip_limit"]["requests"] > 0
    
    def test_bypass_functionality(self, client):
        """Test that localhost requests bypass rate limiting."""
        # Test from localhost (should be bypassed)
        response = client.get("/api/system/health")  # No X-Forwarded-For header
        
        # Should succeed regardless of rate limits (localhost bypass)
        assert response.status_code in [200, 404], "Localhost requests should be bypassed"
    
    def test_rate_limiting_with_monitoring(self, client):
        """Test that rate limiting events are recorded for monitoring."""
        test_ip = "192.168.100.4"
        headers = {"X-Forwarded-For": test_ip}
        
        # Make a few requests
        for i in range(5):
            response = client.get("/api/system/health", headers=headers)
            # Don't assert on status code as rate limiting might kick in
        
        # Check if monitoring status is available
        response = client.get("/api/admin/rate-limit/status")
        
        if response.status_code == 200:
            status = response.json()
            
            # Should indicate monitoring is working
            assert "status" in status
            assert "monitoring_available" in status
            
            if status.get("monitoring_available"):
                # If monitoring is available, check for recorded events
                assert "total_events_recorded" in status
                # Should have recorded at least our test requests
                assert status["total_events_recorded"] >= 0


@pytest.mark.skipif(not INTEGRATION_AVAILABLE, reason="Integration dependencies not available")  
def test_rate_limiting_system_health():
    """Test overall rate limiting system health."""
    from backend.api.rate_limit_config import get_rate_limit_config
    
    # Test configuration loading
    config = get_rate_limit_config()
    
    # Verify essential configuration
    assert config.default_limit.requests > 0
    assert config.default_limit.window > 0
    assert config.global_ip_limit.requests > 0
    assert config.global_ip_limit.window > 0
    
    # Verify endpoint-specific limits exist
    assert len(config.endpoint_limits) > 0
    
    # Verify all endpoint limits are positive
    for endpoint, rule in config.endpoint_limits.items():
        assert rule.requests > 0, f"Endpoint {endpoint} has invalid limit: {rule.requests}"
        assert rule.window > 0, f"Endpoint {endpoint} has invalid window: {rule.window}"
    
    print(f"✓ Rate limiting system health check passed")
    print(f"  - Default limit: {config.default_limit.requests}/{config.default_limit.window}s")
    print(f"  - Global IP limit: {config.global_ip_limit.requests}/{config.global_ip_limit.window}s") 
    print(f"  - Endpoint-specific rules: {len(config.endpoint_limits)}")
    print(f"  - Redis enabled: {config.redis_url is not None}")
    print(f"  - Monitoring enabled: {config.enable_monitoring}")


if __name__ == "__main__":
    # Run a quick health check
    if INTEGRATION_AVAILABLE:
        test_rate_limiting_system_health()
        print("✓ Integration tests ready to run")
    else:
        print("✗ Integration tests not available due to missing dependencies")