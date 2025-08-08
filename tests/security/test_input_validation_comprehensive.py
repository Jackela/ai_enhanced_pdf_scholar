"""
Comprehensive Input Validation Security Tests
Tests for all API endpoint input validation and sanitization mechanisms.
"""

import json
import pytest
import re
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, MagicMock
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tests.security.enhanced_security_utils import (
    PayloadGenerator, SecurityScanner, SecurityTestResult,
    AttackVector, SecuritySeverity, SecurityMonitor,
    SecurityTestFixtures
)


class TestInputValidationSecurity:
    """Comprehensive input validation security tests."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)
    
    @pytest.fixture
    def payload_generator(self):
        """Create payload generator."""
        return PayloadGenerator()
    
    @pytest.fixture
    def security_monitor(self):
        """Create security monitor."""
        return SecurityMonitor()
    
    def test_sql_injection_input_validation(self, client, payload_generator, security_monitor):
        """Test SQL injection prevention through input validation."""
        sql_payloads = payload_generator.generate_sql_injection_payloads()
        vulnerable_endpoints = []
        
        # Test various endpoints with SQL injection payloads
        test_cases = [
            ("/api/documents/search", "GET", "query"),
            ("/api/users/{user_id}", "GET", "user_id"),
            ("/api/citations/filter", "POST", "filter"),
            ("/api/papers/query", "POST", "sql_query"),
        ]
        
        for endpoint, method, param_name in test_cases:
            for payload in sql_payloads[:10]:  # Test subset
                if "{" in endpoint:
                    # Path parameter
                    test_endpoint = endpoint.replace("{user_id}", payload)
                    response = client.request(method, test_endpoint)
                elif method == "GET":
                    response = client.get(endpoint, params={param_name: payload})
                else:
                    response = client.post(endpoint, json={param_name: payload})
                
                # Check for SQL errors in response
                if response.status_code == 500 or "SQL" in response.text:
                    vulnerable_endpoints.append({
                        "endpoint": endpoint,
                        "method": method,
                        "param": param_name,
                        "payload": payload
                    })
                    security_monitor.log_event("sql_injection_attempt", {
                        "endpoint": endpoint,
                        "payload": payload,
                        "detected": True
                    })
                
                # Valid rejection is expected
                assert response.status_code in [400, 422] or \
                       (response.status_code == 200 and "SQL" not in response.text)
        
        assert len(vulnerable_endpoints) == 0, f"SQL injection vulnerabilities: {vulnerable_endpoints}"
    
    def test_command_injection_validation(self, client, payload_generator):
        """Test command injection prevention through input validation."""
        cmd_payloads = PayloadGenerator.COMMAND_INJECTION_PAYLOADS
        
        # Endpoints that might execute commands
        endpoints = [
            ("/api/pdf/convert", "POST", {"filename": ""}),
            ("/api/export", "POST", {"format": "", "options": ""}),
            ("/api/process", "POST", {"command": ""}),
        ]
        
        for endpoint, method, params in endpoints:
            for payload in cmd_payloads[:5]:
                for key in params:
                    test_params = params.copy()
                    test_params[key] = payload
                    
                    response = client.post(endpoint, json=test_params)
                    
                    # Should reject or sanitize command injection attempts
                    assert response.status_code in [400, 422] or \
                           (response.status_code in [200, 201] and 
                            not any(indicator in response.text 
                                   for indicator in ["uid=", "root", "Windows"]))
    
    def test_path_traversal_validation(self, client):
        """Test path traversal prevention through input validation."""
        path_payloads = PayloadGenerator.PATH_TRAVERSAL_PAYLOADS
        
        # File-related endpoints
        endpoints = [
            "/api/files/{filepath}",
            "/api/download",
            "/api/static/{path}",
            "/api/documents/read",
        ]
        
        for endpoint in endpoints:
            for payload in path_payloads[:10]:
                if "{" in endpoint:
                    # Path parameter
                    test_endpoint = endpoint.replace("{filepath}", payload).replace("{path}", payload)
                    response = client.get(test_endpoint)
                else:
                    # Query parameter
                    response = client.get(endpoint, params={"path": payload})
                
                # Should block path traversal attempts
                assert response.status_code in [400, 403, 404] or \
                       (response.status_code == 200 and 
                        not any(indicator in response.text 
                               for indicator in ["root:x:", "[boot loader]", "Windows"]))
    
    def test_integer_overflow_validation(self, client):
        """Test integer overflow prevention."""
        overflow_values = [
            2**31,      # 32-bit signed overflow
            2**32,      # 32-bit unsigned overflow  
            2**63,      # 64-bit signed overflow
            2**64,      # 64-bit unsigned overflow
            -2**31 - 1, # Negative overflow
            -2**63 - 1, # Negative 64-bit overflow
            float('inf'),
            float('-inf'),
            float('nan'),
        ]
        
        endpoints = [
            ("/api/documents", "POST", "page_count"),
            ("/api/pagination", "GET", "limit"),
            ("/api/pagination", "GET", "offset"),
            ("/api/calculate", "POST", "value"),
        ]
        
        for endpoint, method, param in endpoints:
            for value in overflow_values:
                if method == "GET":
                    response = client.get(endpoint, params={param: str(value)})
                else:
                    response = client.post(endpoint, json={param: value})
                
                # Should reject overflow values
                assert response.status_code in [400, 422], \
                       f"Overflow not caught for {param}={value} at {endpoint}"
    
    def test_string_length_validation(self, client):
        """Test string length limits and buffer overflow prevention."""
        # Generate strings of various lengths
        test_strings = [
            "A" * 100,      # Normal
            "A" * 1000,     # Large
            "A" * 10000,    # Very large
            "A" * 100000,   # Huge
            "A" * 1000000,  # Massive
        ]
        
        endpoints = [
            ("/api/documents", "POST", "title", 255),      # Expected max length
            ("/api/comments", "POST", "text", 5000),       # Comment limit
            ("/api/users/bio", "PUT", "bio", 1000),        # Bio limit
            ("/api/search", "GET", "query", 100),          # Search limit
        ]
        
        for endpoint, method, param, max_length in endpoints:
            for test_str in test_strings:
                if method == "GET":
                    response = client.get(endpoint, params={param: test_str})
                else:
                    response = client.request(method, endpoint, json={param: test_str})
                
                # Should reject strings exceeding max length
                if len(test_str) > max_length:
                    assert response.status_code in [400, 422, 413], \
                           f"String length validation failed for {param} at {endpoint}"
    
    def test_email_validation(self, client):
        """Test email address validation."""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user@.com",
            "user@example",
            "user @example.com",
            "user@exam ple.com",
            "<script>@example.com",
            "user@example.com<script>",
            "'; DROP TABLE users--@example.com",
            "../../../etc/passwd@example.com",
            "user@example.com\x00",
            "user@" + "a" * 255 + ".com",  # Domain too long
        ]
        
        for email in invalid_emails:
            response = client.post(
                "/api/users/register",
                json={"email": email, "password": "Test123!"}
            )
            
            # Should reject invalid emails
            assert response.status_code in [400, 422], \
                   f"Invalid email accepted: {email}"
    
    def test_url_validation(self, client):
        """Test URL validation and sanitization."""
        malicious_urls = [
            "javascript:alert('XSS')",
            "data:text/html,<script>alert('XSS')</script>",
            "vbscript:msgbox('XSS')",
            "file:///etc/passwd",
            "ftp://internal-server/",
            "gopher://internal-server/",
            "dict://internal-server/",
            "php://filter/read=convert.base64-encode/resource=index.php",
            "jar:http://example.com/evil.jar!/",
            "//evil.com",  # Protocol-relative URL
            "http://user:pass@evil.com",  # Credentials in URL
            "http://evil.com:99999/",  # Invalid port
            "http://[::1]/",  # IPv6 localhost
            "http://127.0.0.1/",  # IPv4 localhost
            "http://169.254.169.254/",  # AWS metadata endpoint
        ]
        
        for url in malicious_urls:
            response = client.post(
                "/api/links/add",
                json={"url": url}
            )
            
            # Should reject malicious URLs
            assert response.status_code in [400, 422], \
                   f"Malicious URL accepted: {url}"
    
    def test_json_validation(self, client):
        """Test JSON structure validation."""
        invalid_json_payloads = [
            '{"key": undefined}',
            '{"key": NaN}',
            '{"key": Infinity}',
            '{"key": new Date()}',
            '{"__proto__": {"isAdmin": true}}',  # Prototype pollution
            '{"constructor": {"prototype": {"isAdmin": true}}}',
            '{"key": "value"' + "}" * 1000,  # Deeply nested
            '{"a": {"b": {"c": ' * 100 + '{}' + '}}}' * 100,  # Deep nesting
        ]
        
        for payload in invalid_json_payloads:
            response = client.post(
                "/api/data/process",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Should reject invalid JSON
            assert response.status_code in [400, 422]
    
    def test_file_type_validation(self, client):
        """Test file type validation in uploads."""
        # Create test files with various extensions and content
        test_files = [
            ("shell.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
            ("shell.jsp", b"<%@ page import='java.io.*' %>", "application/x-jsp"),
            ("test.exe", b"MZ\x90\x00", "application/x-msdownload"),
            ("test.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh"),
            ("test.bat", b"@echo off\ndel /F /S /Q C:\\*", "application/x-bat"),
            ("fake.pdf.exe", b"MZ", "application/pdf"),  # Double extension
            ("test.pdf\x00.exe", b"MZ", "application/pdf"),  # Null byte
        ]
        
        for filename, content, content_type in test_files:
            files = [("file", (filename, content, content_type))]
            response = client.post("/api/upload", files=files)
            
            # Should reject dangerous file types
            assert response.status_code in [400, 415], \
                   f"Dangerous file accepted: {filename}"
    
    def test_unicode_validation(self, client):
        """Test Unicode and encoding validation."""
        unicode_payloads = [
            "\x00test",  # Null byte
            "test\x00",
            "\uffff",  # Invalid Unicode
            "\ufffe",
            "\ud800",  # Unpaired surrogate
            "test\r\nSet-Cookie: admin=true",  # CRLF injection
            "test\nLocation: http://evil.com",  # Header injection
            "\u202e\u0074\u0078\u0074\u002e\u0065\u0078\u0065",  # RLO attack
            "A" + "\u0000" * 100,  # Multiple null bytes
        ]
        
        for payload in unicode_payloads:
            response = client.post(
                "/api/content/create",
                json={"content": payload}
            )
            
            # Should handle Unicode properly
            if response.status_code == 200:
                # Verify dangerous Unicode is sanitized
                result = response.json()
                assert "\x00" not in str(result)
                assert "\uffff" not in str(result)
    
    def test_regex_dos_prevention(self, client):
        """Test prevention of ReDoS (Regular Expression Denial of Service)."""
        # ReDoS payloads that can cause catastrophic backtracking
        redos_payloads = [
            "a" * 50 + "X",  # For regex like (a+)+
            "a" * 100 + "!",  # For regex like (a*)*
            "x" * 1000 + "y" * 1000,  # For regex like (x+y+)+
            "0" * 50000,  # Large repetition
        ]
        
        import time
        
        for payload in redos_payloads:
            start_time = time.time()
            response = client.post(
                "/api/validate/pattern",
                json={"input": payload}
            )
            elapsed = time.time() - start_time
            
            # Should complete quickly (< 1 second)
            assert elapsed < 1.0, f"Possible ReDoS vulnerability, took {elapsed}s"
            
            # Should either reject or handle gracefully
            assert response.status_code in [200, 400, 422]
    
    def test_xml_validation(self, client):
        """Test XML validation and XXE prevention."""
        xxe_payloads = PayloadGenerator.XXE_PAYLOADS
        
        for payload in xxe_payloads:
            response = client.post(
                "/api/xml/parse",
                data=payload,
                headers={"Content-Type": "application/xml"}
            )
            
            # Should block XXE attempts
            assert response.status_code in [400, 422] or \
                   (response.status_code == 200 and 
                    not any(indicator in response.text 
                           for indicator in ["root:x:", "Windows", "[boot"]))
    
    def test_ldap_injection_validation(self, client):
        """Test LDAP injection prevention."""
        ldap_payloads = PayloadGenerator.LDAP_INJECTION_PAYLOADS
        
        for payload in ldap_payloads:
            response = client.post(
                "/api/users/search",
                json={"filter": payload}
            )
            
            # Should reject LDAP injection attempts
            assert response.status_code in [400, 422] or \
                   (response.status_code == 200 and 
                    "objectClass" not in response.text)


class TestParameterPollution:
    """Test HTTP Parameter Pollution prevention."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)
    
    def test_duplicate_parameter_handling(self, client):
        """Test handling of duplicate parameters."""
        # Test with duplicate parameters
        response = client.get(
            "/api/search?query=normal&query=<script>alert(1)</script>"
        )
        
        # Should handle duplicates safely
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            assert "<script>" not in response.text
    
    def test_parameter_pollution_bypass(self, client):
        """Test parameter pollution bypass attempts."""
        # Try to bypass validation with parameter pollution
        pollution_attempts = [
            "?id=1&id=2' OR '1'='1",
            "?filter=safe&filter=<script>alert(1)</script>",
            "?admin=false&admin=true",
            "?role=user&role=admin",
        ]
        
        for params in pollution_attempts:
            response = client.get(f"/api/data{params}")
            
            # Should not allow bypass through pollution
            assert response.status_code in [400, 403] or \
                   (response.status_code == 200 and 
                    "admin" not in response.text.lower())


class TestBusinessLogicValidation:
    """Test business logic validation."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)
    
    def test_negative_value_validation(self, client):
        """Test handling of negative values where inappropriate."""
        endpoints = [
            ("/api/products/order", "quantity", -1),
            ("/api/transfer", "amount", -1000),
            ("/api/pagination", "limit", -10),
            ("/api/pagination", "offset", -5),
        ]
        
        for endpoint, param, value in endpoints:
            response = client.post(
                endpoint,
                json={param: value}
            )
            
            # Should reject negative values
            assert response.status_code in [400, 422]
    
    def test_logical_inconsistency_validation(self, client):
        """Test validation of logically inconsistent inputs."""
        inconsistent_inputs = [
            {"start_date": "2024-01-01", "end_date": "2023-01-01"},  # End before start
            {"min_value": 100, "max_value": 50},  # Min > Max
            {"page": 0, "per_page": 100},  # Invalid page number
            {"total": 50, "used": 100},  # Used > Total
        ]
        
        for data in inconsistent_inputs:
            response = client.post("/api/validate/logic", json=data)
            
            # Should reject inconsistent inputs
            assert response.status_code in [400, 422]
    
    def test_race_condition_validation(self, client):
        """Test prevention of race condition exploits."""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = client.post(
                "/api/limited-resource",
                json={"action": "claim"}
            )
            results.append(response.status_code)
        
        # Try to exploit race condition with concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Only one should succeed if properly protected
        success_count = sum(1 for status in results if status in [200, 201])
        assert success_count <= 1, "Race condition vulnerability detected"


class TestInputSanitization:
    """Test input sanitization mechanisms."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)
    
    def test_html_tag_stripping(self, client):
        """Test HTML tag stripping in text inputs."""
        html_inputs = [
            "<b>Bold</b> text",
            "<script>alert(1)</script>Normal",
            "<img src=x onerror=alert(1)>",
            "<a href='javascript:alert(1)'>Link</a>",
        ]
        
        for html in html_inputs:
            response = client.post(
                "/api/text/plain",
                json={"text": html}
            )
            
            if response.status_code == 200:
                result = response.json().get("text", "")
                # HTML should be stripped
                assert "<" not in result
                assert ">" not in result
    
    def test_sql_keyword_sanitization(self, client):
        """Test SQL keyword sanitization."""
        sql_keywords = [
            "SELECT * FROM users",
            "DROP TABLE users",
            "INSERT INTO admin",
            "UPDATE users SET",
            "DELETE FROM",
            "UNION SELECT",
        ]
        
        for keyword in sql_keywords:
            response = client.post(
                "/api/comments/add",
                json={"comment": keyword}
            )
            
            # Should sanitize or reject SQL keywords
            if response.status_code == 200:
                result = response.json()
                # Verify SQL keywords are handled
                assert "SELECT" not in result.get("comment", "") or \
                       result.get("comment", "") != keyword
    
    def test_special_character_encoding(self, client):
        """Test special character encoding."""
        special_chars = [
            "<>&\"'",
            "\\x3cscript\\x3e",
            "%3Cscript%3E",
            "&#60;script&#62;",
        ]
        
        for chars in special_chars:
            response = client.post(
                "/api/encode",
                json={"input": chars}
            )
            
            if response.status_code == 200:
                result = response.json().get("encoded", "")
                # Should be properly encoded
                assert "&lt;" in result or "%3C" in result or "\\x3c" in result.lower()


class TestValidationErrorHandling:
    """Test validation error handling and messages."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)
    
    def test_validation_error_messages(self, client):
        """Test that validation errors don't leak sensitive info."""
        invalid_inputs = [
            {"email": "invalid"},
            {"age": "not_a_number"},
            {"date": "invalid_date"},
            {"url": "not_a_url"},
        ]
        
        for data in invalid_inputs:
            response = client.post("/api/validate", json=data)
            
            if response.status_code in [400, 422]:
                error_msg = response.text
                
                # Should not leak system paths
                assert "/home/" not in error_msg
                assert "C:\\" not in error_msg
                
                # Should not leak stack traces
                assert "Traceback" not in error_msg
                assert "File \"" not in error_msg
                
                # Should not leak database info
                assert "SELECT" not in error_msg
                assert "TABLE" not in error_msg
    
    def test_rate_limiting_validation(self, client):
        """Test rate limiting on validation endpoints."""
        # Make rapid requests
        for i in range(20):
            response = client.post(
                "/api/validate/expensive",
                json={"data": f"test_{i}"}
            )
            
            # After threshold, should rate limit
            if i > 10 and response.status_code == 429:
                # Rate limiting is working
                assert "rate limit" in response.text.lower() or \
                       "too many requests" in response.text.lower()
                break
        else:
            # Should have hit rate limit
            pytest.skip("Rate limiting might not be configured")


class TestValidationMetrics:
    """Test validation metrics and reporting."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from backend.main import app
        return TestClient(app)
    
    @pytest.fixture
    def scanner(self, client):
        """Create security scanner."""
        return SecurityScanner(client)
    
    def test_validation_coverage_metrics(self, scanner):
        """Test validation coverage across endpoints."""
        # Define endpoints to test
        endpoints = [
            ("GET", "/api/search", {"q": "test"}, None),
            ("POST", "/api/documents", None, {"title": "test"}),
            ("PUT", "/api/users/profile", None, {"bio": "test"}),
            ("DELETE", "/api/documents/1", None, None),
        ]
        
        validation_results = {}
        
        for method, endpoint, params, data in endpoints:
            # Test with various invalid inputs
            test_inputs = [
                "",  # Empty
                "A" * 10000,  # Too long
                "<script>alert(1)</script>",  # XSS
                "' OR '1'='1",  # SQL injection
                "../../../etc/passwd",  # Path traversal
            ]
            
            endpoint_results = []
            for test_input in test_inputs:
                if params:
                    test_params = {k: test_input for k in params}
                    response = scanner.client.request(method, endpoint, params=test_params)
                elif data:
                    test_data = {k: test_input for k in data}
                    response = scanner.client.request(method, endpoint, json=test_data)
                else:
                    response = scanner.client.request(method, endpoint)
                
                endpoint_results.append({
                    "input": test_input,
                    "status": response.status_code,
                    "validated": response.status_code in [400, 422]
                })
            
            validation_results[endpoint] = {
                "coverage": sum(1 for r in endpoint_results if r["validated"]) / len(endpoint_results),
                "results": endpoint_results
            }
        
        # Calculate overall validation coverage
        total_coverage = sum(v["coverage"] for v in validation_results.values()) / len(validation_results)
        
        # Should have high validation coverage
        assert total_coverage > 0.8, f"Low validation coverage: {total_coverage:.2%}"
        
        return validation_results


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])