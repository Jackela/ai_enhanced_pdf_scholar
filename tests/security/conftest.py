"""
Security Testing Configuration and Fixtures
Shared fixtures and configuration for all security tests.
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import security testing utilities
from tests.security.enhanced_security_utils import (
    AsyncSecurityTester,
    PayloadGenerator,
    SecurityMonitor,
    SecurityScanner,
    SecurityTestFixtures,
)


# Configure pytest for security testing
def pytest_configure(config):
    """Configure pytest for security testing."""
    config.addinivalue_line(
        "markers", "security: mark test as security test"
    )
    config.addinivalue_line(
        "markers", "critical: mark test as critical security test"
    )
    config.addinivalue_line(
        "markers", "regression: mark test as security regression test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow security test"
    )


# Session-scoped fixtures
@pytest.fixture(scope="session")
def app():
    """Create FastAPI application for testing."""
    from backend.main import app
    return app


@pytest.fixture(scope="session")
def security_config():
    """Security testing configuration."""
    return {
        "rate_limit_threshold": 10,
        "max_payload_size": 1024 * 1024,  # 1MB
        "session_timeout": 3600,
        "max_login_attempts": 5,
        "security_headers": [
            "Content-Security-Policy",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security"
        ],
        "blocked_file_extensions": [
            ".exe", ".sh", ".bat", ".cmd", ".com",
            ".scr", ".vbs", ".js", ".jar", ".zip"
        ],
        "allowed_origins": [
            "http://localhost:3000",
            "http://localhost:8000"
        ]
    }


# Function-scoped fixtures
@pytest.fixture
def client(app):
    """Create test client for each test."""
    return TestClient(app)


@pytest.fixture
def authenticated_client(client):
    """Create authenticated test client."""
    # Perform login
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "Test123!"}
    )

    if response.status_code == 200:
        token = response.json().get("access_token")
        client.headers["Authorization"] = f"Bearer {token}"

    return client


@pytest.fixture
def admin_client(client):
    """Create admin authenticated test client."""
    # Perform admin login
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin123!"}
    )

    if response.status_code == 200:
        token = response.json().get("access_token")
        client.headers["Authorization"] = f"Bearer {token}"

    return client


@pytest.fixture
def db_session():
    """Create database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    from backend.database import Base
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def security_monitor():
    """Create security monitor for tracking events."""
    return SecurityMonitor()


@pytest.fixture
def security_scanner(client):
    """Create security scanner."""
    return SecurityScanner(client)


@pytest.fixture
def payload_generator():
    """Create payload generator."""
    return PayloadGenerator()


@pytest.fixture
def async_tester(client):
    """Create async security tester."""
    return AsyncSecurityTester()


@pytest.fixture
def mock_user():
    """Create mock user for testing."""
    return SecurityTestFixtures.create_mock_user()


@pytest.fixture
def mock_session():
    """Create mock session for testing."""
    return SecurityTestFixtures.create_mock_session()


@pytest.fixture
def malicious_pdf():
    """Create malicious PDF for testing."""
    return SecurityTestFixtures.create_malicious_pdf()


@pytest.fixture
def malicious_files():
    """Create various malicious files for testing."""
    return PayloadGenerator.generate_malicious_files()


# Async fixtures
@pytest.fixture
async def async_client(app):
    """Create async test client."""
    from httpx import AsyncClient

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# Test data fixtures
@pytest.fixture
def sql_injection_payloads():
    """Get SQL injection test payloads."""
    return PayloadGenerator.SQL_INJECTION_PAYLOADS


@pytest.fixture
def xss_payloads():
    """Get XSS test payloads."""
    return PayloadGenerator.XSS_PAYLOADS


@pytest.fixture
def path_traversal_payloads():
    """Get path traversal test payloads."""
    return PayloadGenerator.PATH_TRAVERSAL_PAYLOADS


@pytest.fixture
def command_injection_payloads():
    """Get command injection test payloads."""
    return PayloadGenerator.COMMAND_INJECTION_PAYLOADS


# Helper fixtures
@pytest.fixture
def temp_upload_dir(tmp_path):
    """Create temporary upload directory."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    return upload_dir


@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    mock = MagicMock()
    mock.send_email = MagicMock(return_value=True)
    mock.send_alert = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_cache():
    """Mock cache for testing."""
    cache = {}

    mock = MagicMock()
    mock.get = lambda key: cache.get(key)
    mock.set = lambda key, value, ttl=None: cache.update({key: value})
    mock.delete = lambda key: cache.pop(key, None)
    mock.clear = lambda: cache.clear()

    return mock


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Clean up after each test."""
    yield
    # Cleanup code here if needed


# Performance monitoring
@pytest.fixture
def performance_monitor():
    """Monitor test performance."""
    import time

    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.measurements = []

        def start(self):
            self.start_time = time.time()

        def stop(self, label=""):
            if self.start_time:
                elapsed = time.time() - self.start_time
                self.measurements.append({
                    "label": label,
                    "time": elapsed
                })
                return elapsed
            return 0

        def get_report(self):
            return {
                "total_measurements": len(self.measurements),
                "measurements": self.measurements,
                "total_time": sum(m["time"] for m in self.measurements)
            }

    return PerformanceMonitor()


# Security baseline fixture
@pytest.fixture
def security_baseline():
    """Load security baseline for regression testing."""
    baseline_file = Path("tests/security/security_baseline.json")

    if baseline_file.exists():
        import json
        with open(baseline_file) as f:
            return json.load(f)

    # Return default baseline
    return {
        "version": "1.0.0",
        "vulnerabilities": {},
        "security_headers": {
            "Content-Security-Policy": True,
            "X-Frame-Options": True,
            "X-Content-Type-Options": True
        },
        "rate_limits": {
            "/api/auth/login": 5,
            "/api/search": 30
        }
    }


# Report generation fixture
@pytest.fixture(scope="session")
def security_report(request):
    """Generate security test report at end of session."""
    import json
    from datetime import datetime

    report = {
        "timestamp": datetime.now().isoformat(),
        "tests": [],
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0
        }
    }

    def finalize():
        # Generate final report
        report_dir = Path("tests/security/reports")
        report_dir.mkdir(parents=True, exist_ok=True)

        report_file = report_dir / f"security_test_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nSecurity test report saved to: {report_file}")
        print(f"Summary: {report['summary']}")

    request.addfinalizer(finalize)
    return report


# Custom assertions
class SecurityAssertions:
    """Custom assertions for security testing."""

    @staticmethod
    def assert_no_sql_injection(response, payload):
        """Assert response doesn't indicate SQL injection."""
        assert response.status_code not in [500], \
               f"Server error with SQL payload: {payload}"

        error_indicators = [
            "SQL", "syntax", "mysql", "postgresql", "sqlite",
            "ORA-", "DB2", "Microsoft"
        ]

        response_text = response.text.lower()
        for indicator in error_indicators:
            assert indicator.lower() not in response_text, \
                   f"SQL error indicator found: {indicator}"

    @staticmethod
    def assert_no_xss(response, payload):
        """Assert response doesn't contain XSS."""
        if payload in response.text:
            # Check if properly escaped
            assert "&lt;" in response.text or \
                   "&gt;" in response.text or \
                   "\\u003c" in response.text.lower(), \
                   f"Unescaped XSS payload in response: {payload}"

    @staticmethod
    def assert_proper_rate_limiting(responses):
        """Assert proper rate limiting behavior."""
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes, "Rate limiting not triggered"

        # Check for proper headers
        limited_response = next(r for r in responses if r.status_code == 429)
        assert "Retry-After" in limited_response.headers or \
               "X-RateLimit-Reset" in limited_response.headers, \
               "Rate limit headers missing"

    @staticmethod
    def assert_secure_headers(response):
        """Assert security headers are present."""
        important_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection"
        ]

        for header in important_headers:
            assert header in response.headers, \
                   f"Security header missing: {header}"


@pytest.fixture
def assertions():
    """Provide custom security assertions."""
    return SecurityAssertions()


# Environment-specific configuration
@pytest.fixture
def test_environment():
    """Get test environment configuration."""
    env = os.getenv("TEST_ENV", "local")

    configs = {
        "local": {
            "base_url": "http://localhost:8000",
            "timeout": 30,
            "parallel_tests": 4
        },
        "ci": {
            "base_url": "http://test-server:8000",
            "timeout": 60,
            "parallel_tests": 2
        },
        "staging": {
            "base_url": "https://staging.example.com",
            "timeout": 45,
            "parallel_tests": 1
        }
    }

    return configs.get(env, configs["local"])


# Parameterized test data
def pytest_generate_tests(metafunc):
    """Generate parameterized tests for security testing."""

    if "attack_payload" in metafunc.fixturenames:
        # Generate test cases for various attack payloads
        payloads = []
        payloads.extend([("sql", p) for p in PayloadGenerator.SQL_INJECTION_PAYLOADS[:5]])
        payloads.extend([("xss", p) for p in PayloadGenerator.XSS_PAYLOADS[:5]])
        payloads.extend([("path", p) for p in PayloadGenerator.PATH_TRAVERSAL_PAYLOADS[:5]])

        metafunc.parametrize("attack_payload", payloads)

    if "endpoint" in metafunc.fixturenames:
        # Generate test cases for various endpoints
        endpoints = [
            "/api/search",
            "/api/login",
            "/api/upload",
            "/api/documents",
            "/api/users"
        ]
        metafunc.parametrize("endpoint", endpoints)


# Note: Markers are defined in pytest.ini, not here


# Test collection hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection for security tests."""
    # Add markers based on test names
    for item in items:
        if "security" in item.nodeid:
            item.add_marker(pytest.mark.security)

        if "critical" in item.name or "auth" in item.name:
            item.add_marker(pytest.mark.critical)

        if "regression" in item.name:
            item.add_marker(pytest.mark.regression)

        if "ddos" in item.name or "brute_force" in item.name:
            item.add_marker(pytest.mark.slow)
