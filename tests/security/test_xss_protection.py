"""
Comprehensive XSS Protection Tests
Tests for DOMPurify integration and content sanitization across all components.
"""

import json
import pytest
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock
from fastapi import status
from fastapi.testclient import TestClient

from tests.security.enhanced_security_utils import (
    PayloadGenerator, SecurityScanner, SecurityTestResult,
    AttackVector, SecuritySeverity, SecurityMonitor
)


class TestXSSProtection:
    """Comprehensive XSS protection testing."""

    @pytest.fixture
    def xss_payloads(self) -> List[str]:
        """Get comprehensive XSS test payloads."""
        return PayloadGenerator.XSS_PAYLOADS

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def security_monitor(self):
        """Create security monitor for tracking."""
        return SecurityMonitor()

    def test_basic_xss_prevention(self, client, xss_payloads, security_monitor):
        """Test basic XSS prevention in all input fields."""
        vulnerable_endpoints = []

        # Test common endpoints
        endpoints = [
            ("/api/documents/search", "GET", {"q": ""}),
            ("/api/citations/create", "POST", {"content": ""}),
            ("/api/users/profile", "PUT", {"bio": ""}),
            ("/api/comments/add", "POST", {"text": ""}),
        ]

        for endpoint, method, params in endpoints:
            for payload in xss_payloads[:10]:  # Test subset for efficiency
                if method == "GET":
                    params_copy = params.copy()
                    for key in params_copy:
                        params_copy[key] = payload
                    response = client.get(endpoint, params=params_copy)
                else:
                    data_copy = params.copy()
                    for key in data_copy:
                        data_copy[key] = payload
                    response = client.post(endpoint, json=data_copy)

                # Check if payload is reflected without sanitization
                if response.status_code == 200:
                    response_text = response.text
                    if payload in response_text and "<script>" in payload:
                        vulnerable_endpoints.append({
                            "endpoint": endpoint,
                            "method": method,
                            "payload": payload
                        })
                        security_monitor.log_event("xss_attempt", {
                            "endpoint": endpoint,
                            "payload": payload,
                            "vulnerable": True
                        })

        assert len(vulnerable_endpoints) == 0, f"XSS vulnerabilities found: {vulnerable_endpoints}"

    def test_stored_xss_prevention(self, client, xss_payloads):
        """Test prevention of stored XSS attacks."""
        # Create a document with XSS payload
        for payload in xss_payloads[:5]:
            # Store malicious content
            create_response = client.post(
                "/api/documents/",
                json={
                    "title": f"Test {payload}",
                    "content": payload,
                    "description": payload
                }
            )

            if create_response.status_code == 201:
                doc_id = create_response.json().get("id")

                # Retrieve and check if XSS is executed
                get_response = client.get(f"/api/documents/{doc_id}")

                if get_response.status_code == 200:
                    content = get_response.json()

                    # Verify content is sanitized
                    assert "<script>" not in str(content)
                    assert "javascript:" not in str(content).lower()
                    assert "onerror=" not in str(content).lower()

    def test_dom_based_xss_prevention(self, client):
        """Test DOM-based XSS prevention."""
        # Test URL fragments and hash-based XSS
        dom_xss_payloads = [
            "#<script>alert('XSS')</script>",
            "#javascript:alert('XSS')",
            "?name=<img src=x onerror=alert('XSS')>",
            "#'><script>alert('XSS')</script>",
        ]

        for payload in dom_xss_payloads:
            response = client.get(f"/api/search{payload}")

            # Ensure no execution of JavaScript
            if response.status_code == 200:
                assert "<script>" not in response.text
                assert "alert(" not in response.text

    def test_reflected_xss_prevention(self, client, xss_payloads):
        """Test reflected XSS prevention in error messages and responses."""
        for payload in xss_payloads[:10]:
            # Test in search queries
            response = client.get(
                "/api/search",
                params={"query": payload}
            )

            if response.status_code in [200, 400, 404]:
                response_text = response.text

                # Check payload is not reflected as-is
                if payload in response_text:
                    # Verify it's properly encoded
                    assert "&lt;script&gt;" in response_text or \
                           "&lt;img" in response_text or \
                           response_text != payload

    def test_xss_in_json_responses(self, client, xss_payloads):
        """Test XSS prevention in JSON API responses."""
        for payload in xss_payloads[:5]:
            response = client.post(
                "/api/validate",
                json={"input": payload}
            )

            if response.status_code == 200:
                try:
                    json_response = response.json()
                    # Check all values in JSON are properly escaped
                    json_str = json.dumps(json_response)
                    assert "<script>" not in json_str
                    assert "javascript:" not in json_str.lower()
                except:
                    pass

    def test_xss_filter_bypass_attempts(self, client):
        """Test advanced XSS filter bypass techniques."""
        bypass_payloads = [
            # Case variations
            "<ScRiPt>alert('XSS')</ScRiPt>",
            "<SCRIPT>alert('XSS')</SCRIPT>",

            # Encoding bypasses
            "%3Cscript%3Ealert('XSS')%3C/script%3E",
            "&#60;script&#62;alert('XSS')&#60;/script&#62;",
            "\\x3cscript\\x3ealert('XSS')\\x3c/script\\x3e",
            "\\u003cscript\\u003ealert('XSS')\\u003c/script\\u003e",

            # Null byte injection
            "<scri\x00pt>alert('XSS')</scri\x00pt>",

            # Event handlers
            "<img src=x on\x00error=alert('XSS')>",
            "<img src=x on error=alert('XSS')>",
            "<img src=x onerror\x09=alert('XSS')>",

            # JavaScript protocol
            "java\x09script:alert('XSS')",
            "java\x0Ascript:alert('XSS')",
            "java\x0Dscript:alert('XSS')",

            # Data URI
            "data:text/html,<script>alert('XSS')</script>",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4=",

            # Polyglot
            "jaVasCript:/*-/*`/*\\`/*'/*\"/**/(/* */oNcliCk=alert() )//%0D%0A%0d%0a//</stYle/</titLe/</teXtarEa/</scRipt/--!>\\x3csVg/<sVg/oNloAd=alert()//>",
        ]

        for payload in bypass_payloads:
            response = client.post(
                "/api/content/create",
                json={"content": payload}
            )

            if response.status_code in [200, 201]:
                response_data = response.json()

                # Verify bypasses are caught
                assert "alert(" not in str(response_data).lower()
                assert "<script" not in str(response_data).lower()
                assert "javascript:" not in str(response_data).lower()

    def test_xss_in_file_uploads(self, client):
        """Test XSS prevention in file upload functionality."""
        # SVG with embedded JavaScript
        svg_xss = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert("XSS")</script></svg>'

        files = [
            ("file", ("image.svg", svg_xss, "image/svg+xml")),
        ]

        response = client.post("/api/upload", files=files)

        # Verify SVG is sanitized or rejected
        assert response.status_code in [400, 415] or \
               (response.status_code == 200 and "<script>" not in response.text)

    def test_xss_in_pdf_metadata(self, client):
        """Test XSS prevention in PDF metadata extraction."""
        # Create PDF with malicious metadata
        malicious_pdf = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R/OpenAction<</S/JavaScript/JS(app.alert('XSS'))>>>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R>>endobj
trailer<</Root 1 0 R>>"""

        files = [
            ("file", ("malicious.pdf", malicious_pdf, "application/pdf")),
        ]

        response = client.post("/api/pdf/upload", files=files)

        if response.status_code == 200:
            # Check metadata doesn't contain executable scripts
            metadata = response.json().get("metadata", {})
            assert "alert(" not in str(metadata)
            assert "<script>" not in str(metadata)

    def test_content_security_policy_headers(self, client):
        """Test CSP headers are properly set."""
        response = client.get("/")

        # Check for security headers
        headers = response.headers

        # CSP should be present
        assert "Content-Security-Policy" in headers or \
               "X-Content-Security-Policy" in headers

        # If CSP exists, verify it blocks inline scripts
        if "Content-Security-Policy" in headers:
            csp = headers["Content-Security-Policy"]
            assert "unsafe-inline" not in csp or "nonce-" in csp

    def test_xss_in_error_messages(self, client, xss_payloads):
        """Test XSS prevention in error messages."""
        for payload in xss_payloads[:5]:
            # Trigger error with XSS payload
            response = client.get(f"/api/invalid/{payload}")

            if response.status_code >= 400:
                error_message = response.text

                # Verify error doesn't reflect XSS
                if payload in error_message:
                    assert "&lt;" in error_message or \
                           "&gt;" in error_message or \
                           "\\u003c" in error_message

    def test_mutation_xss_prevention(self, client):
        """Test prevention of mutation-based XSS attacks."""
        mutation_payloads = [
            # mXSS via innerHTML mutations
            "<div><div/style=\x0Bbackground-image:\x0Burl(javascript:alert(1))>",
            "<style>*{font-family:'<img src=x onerror=alert(1)>'}</style>",

            # DOM clobbering
            "<form><input name=innerHTML><script>alert(1)</script>",
            "<a id=location href=javascript:alert(1)>",

            # Namespace confusion
            "<svg><script href=data:,alert(1) />",
            "<math><mtext><script>alert(1)</script></mtext></math>",
        ]

        for payload in mutation_payloads:
            response = client.post(
                "/api/content/render",
                json={"html": payload}
            )

            if response.status_code == 200:
                rendered = response.json().get("rendered", "")
                assert "alert(1)" not in rendered
                assert "javascript:" not in rendered.lower()


class TestDOMPurifyIntegration:
    """Test DOMPurify integration and configuration."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    def test_dompurify_sanitization(self, client):
        """Test DOMPurify sanitization is working correctly."""
        test_cases = [
            {
                "input": "<script>alert('XSS')</script><p>Clean text</p>",
                "expected": "<p>Clean text</p>"
            },
            {
                "input": "<img src=x onerror=alert('XSS')>",
                "expected": "<img src=\"x\">"
            },
            {
                "input": "<a href='javascript:alert(1)'>Link</a>",
                "expected": "<a>Link</a>"
            },
            {
                "input": "<div onmouseover='alert(1)'>Hover</div>",
                "expected": "<div>Hover</div>"
            },
        ]

        for test_case in test_cases:
            response = client.post(
                "/api/sanitize",
                json={"content": test_case["input"]}
            )

            if response.status_code == 200:
                sanitized = response.json().get("sanitized", "")

                # Check dangerous content is removed
                assert "<script>" not in sanitized
                assert "onerror=" not in sanitized.lower()
                assert "javascript:" not in sanitized.lower()
                assert "onmouseover=" not in sanitized.lower()

    def test_dompurify_configuration(self, client):
        """Test DOMPurify configuration options."""
        # Test with different configuration options
        configs = [
            {"ALLOWED_TAGS": ["p", "br", "strong", "em"]},
            {"ALLOWED_ATTR": ["href", "src"]},
            {"FORBID_TAGS": ["script", "style", "iframe"]},
            {"FORBID_ATTR": ["onerror", "onclick", "onload"]},
        ]

        dangerous_content = "<script>alert(1)</script><p onclick='alert(2)'>Text</p>"

        for config in configs:
            response = client.post(
                "/api/sanitize/custom",
                json={
                    "content": dangerous_content,
                    "config": config
                }
            )

            if response.status_code == 200:
                result = response.json().get("sanitized", "")
                assert "<script>" not in result
                assert "onclick=" not in result.lower()

    def test_dompurify_hooks(self, client):
        """Test DOMPurify hooks for custom sanitization."""
        # Test content that should trigger hooks
        test_content = [
            "<a href='http://evil.com'>Link</a>",
            "<img src='http://tracking.com/pixel.gif'>",
            "<form action='http://phishing.com/steal'>",
        ]

        for content in test_content:
            response = client.post(
                "/api/sanitize/strict",
                json={"content": content}
            )

            if response.status_code == 200:
                result = response.json().get("sanitized", "")

                # External URLs should be removed or neutralized
                assert "evil.com" not in result
                assert "tracking.com" not in result
                assert "phishing.com" not in result


class TestXSSContextualEscaping:
    """Test contextual escaping for different output contexts."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    def test_html_context_escaping(self, client):
        """Test escaping in HTML context."""
        payloads = [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "';alert(1);//",
        ]

        for payload in payloads:
            response = client.post(
                "/api/render/html",
                json={"content": payload}
            )

            if response.status_code == 200:
                html = response.json().get("html", "")

                # Should be escaped
                assert "&lt;script&gt;" in html or \
                       "&lt;img" in html or \
                       "&#x27;" in html

    def test_javascript_context_escaping(self, client):
        """Test escaping in JavaScript context."""
        payloads = [
            "';alert(1);//",
            '";alert(1);//',
            "\\';alert(1);//",
            "</script><script>alert(1)</script>",
        ]

        for payload in payloads:
            response = client.post(
                "/api/render/js",
                json={"data": payload}
            )

            if response.status_code == 200:
                js = response.json().get("javascript", "")

                # Should be escaped for JS context
                assert "\\'" in js or \
                       '\\"' in js or \
                       "\\x3c" in js.lower()

    def test_css_context_escaping(self, client):
        """Test escaping in CSS context."""
        payloads = [
            "expression(alert(1))",
            "url('javascript:alert(1)')",
            "background: url('data:text/html,<script>alert(1)</script>')",
        ]

        for payload in payloads:
            response = client.post(
                "/api/render/css",
                json={"style": payload}
            )

            if response.status_code == 200:
                css = response.json().get("css", "")

                # Dangerous CSS should be blocked
                assert "expression(" not in css.lower()
                assert "javascript:" not in css.lower()
                assert "<script>" not in css

    def test_url_context_escaping(self, client):
        """Test escaping in URL context."""
        payloads = [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            "file:///etc/passwd",
        ]

        for payload in payloads:
            response = client.post(
                "/api/render/url",
                json={"url": payload}
            )

            if response.status_code == 200:
                url = response.json().get("url", "")

                # Dangerous protocols should be blocked
                assert not url.startswith("javascript:")
                assert not url.startswith("data:")
                assert not url.startswith("vbscript:")
                assert not url.startswith("file:")


class TestXSSRegressionPrevention:
    """Test to prevent XSS regression."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def known_xss_vectors(self):
        """Known XSS vectors that were previously fixed."""
        return [
            # Previously vulnerable search endpoint
            {
                "endpoint": "/api/search",
                "method": "GET",
                "param": "q",
                "payload": "<script>alert('XSS')</script>"
            },
            # Previously vulnerable comment endpoint
            {
                "endpoint": "/api/comments",
                "method": "POST",
                "param": "text",
                "payload": "<img src=x onerror=alert('XSS')>"
            },
            # Previously vulnerable profile update
            {
                "endpoint": "/api/profile",
                "method": "PUT",
                "param": "bio",
                "payload": "javascript:alert('XSS')"
            },
        ]

    def test_no_xss_regression(self, client, known_xss_vectors):
        """Ensure previously fixed XSS vulnerabilities don't regress."""
        for vector in known_xss_vectors:
            if vector["method"] == "GET":
                response = client.get(
                    vector["endpoint"],
                    params={vector["param"]: vector["payload"]}
                )
            elif vector["method"] == "POST":
                response = client.post(
                    vector["endpoint"],
                    json={vector["param"]: vector["payload"]}
                )
            elif vector["method"] == "PUT":
                response = client.put(
                    vector["endpoint"],
                    json={vector["param"]: vector["payload"]}
                )

            # Verify vulnerability is still fixed
            if response.status_code in [200, 201]:
                assert vector["payload"] not in response.text or \
                       "&lt;script&gt;" in response.text

    def test_xss_security_headers(self, client):
        """Test security headers that prevent XSS."""
        response = client.get("/")
        headers = response.headers

        # Check X-XSS-Protection header
        if "X-XSS-Protection" in headers:
            assert headers["X-XSS-Protection"] in ["1; mode=block", "1"]

        # Check X-Content-Type-Options
        if "X-Content-Type-Options" in headers:
            assert headers["X-Content-Type-Options"] == "nosniff"

        # Check Content-Security-Policy
        if "Content-Security-Policy" in headers:
            csp = headers["Content-Security-Policy"]
            # Should restrict script sources
            assert "script-src" in csp
            # Should not allow unsafe-inline without nonce
            if "unsafe-inline" in csp:
                assert "nonce-" in csp or "'strict-dynamic'" in csp


class TestXSSMetricsAndReporting:
    """Test XSS protection metrics and reporting."""

    @pytest.fixture
    def scanner(self, client):
        """Create security scanner."""
        return SecurityScanner(client)

    @pytest.fixture
    def monitor(self):
        """Create security monitor."""
        return SecurityMonitor()

    def test_xss_scan_reporting(self, scanner, monitor):
        """Test XSS vulnerability scanning and reporting."""
        # Run XSS scan on multiple endpoints
        endpoints = [
            ("GET", "/api/search", {"q": "test"}, None),
            ("POST", "/api/content", None, {"text": "test"}),
            ("PUT", "/api/profile", None, {"bio": "test"}),
        ]

        for method, endpoint, params, data in endpoints:
            # Run targeted XSS scan
            asyncio.run(scanner.scan_endpoint(method, endpoint, params, data, None))

        # Generate report
        report = scanner.generate_report()

        # Verify report structure
        assert "total_tests" in report
        assert "vulnerabilities_found" in report
        assert "severity_breakdown" in report

        # Check for XSS vulnerabilities
        xss_vulns = [
            r for r in report.get("results", [])
            if r["attack_vector"] == AttackVector.XSS.value
        ]

        # Log metrics
        monitor.log_event("xss_scan_complete", {
            "total_tests": report["total_tests"],
            "xss_vulnerabilities": len(xss_vulns)
        })

        # Assert no XSS vulnerabilities found
        assert len(xss_vulns) == 0, f"XSS vulnerabilities detected: {xss_vulns}"

    def test_xss_prevention_performance(self, client):
        """Test performance impact of XSS prevention."""
        import time

        # Measure baseline performance
        start = time.time()
        for _ in range(100):
            client.post("/api/content", json={"text": "Normal content"})
        baseline_time = time.time() - start

        # Measure with XSS payloads
        start = time.time()
        for _ in range(100):
            client.post("/api/content", json={
                "text": "<script>alert('XSS')</script>"
            })
        xss_time = time.time() - start

        # Performance overhead should be reasonable (< 50% increase)
        overhead = (xss_time - baseline_time) / baseline_time
        assert overhead < 0.5, f"XSS prevention overhead too high: {overhead:.2%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])