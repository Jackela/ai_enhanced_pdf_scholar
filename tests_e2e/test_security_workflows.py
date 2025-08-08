"""
Security Workflows E2E Tests

Comprehensive security testing including XSS, injection, authentication, and authorization.
"""

import pytest
from playwright.sync_api import Page, expect
import time
import json
from pathlib import Path
from fixtures import *


class TestSecurityWorkflows:
    """Test security measures and vulnerability prevention."""
    
    @pytest.mark.e2e
    @pytest.mark.security
    def test_xss_prevention(
        self,
        page: Page,
        page_helper,
        api_client,
        security_test_payloads,
        web_server
    ):
        """Test XSS (Cross-Site Scripting) prevention."""
        page.goto(f"{web_server}/library`)
        
        xss_payloads = security_test_payloads['xss']
        
        for payload in xss_payloads:
            # Test in search input
            search_input = page.locator('[data-testid="library-search"]')
            search_input.fill(payload)
            search_input.press("Enter")
            
            # Verify no script execution
            # Check for alert dialogs
            alert_present = False
            try:
                page.wait_for_event("dialog", timeout=1000)
                alert_present = True
            except:
                alert_present = False
            
            assert not alert_present, f"XSS vulnerability detected with payload: {payload}"
            
            # Verify payload is escaped in display
            search_results = page.locator('[data-testid="search-term-display"]')
            if search_results.is_visible():
                displayed_text = search_results.text_content()
                # Verify HTML entities are escaped
                assert "<script>" not in displayed_text
                assert "javascript:" not in displayed_text
            
            # Clear search
            search_input.clear()
        
        # Test XSS in document upload
        page.goto(f"{web_server}/upload")
        
        for payload in xss_payloads[:3]:  # Test subset for upload
            title_input = page.locator('[data-testid="document-title"]')
            title_input.fill(payload)
            
            description_input = page.locator('[data-testid="document-description"]')
            description_input.fill(payload)
            
            # Verify no execution on blur/change
            page.click('body')
            
            # Check for alert
            alert_present = False
            try:
                page.wait_for_event("dialog", timeout=1000)
                alert_present = True
            except:
                alert_present = False
            
            assert not alert_present, f"XSS in upload form with payload: {payload}"
            
            # Clear inputs
            title_input.clear()
            description_input.clear()
        
        # Test XSS in RAG queries
        page.goto(f"{web_server}/rag")
        
        for payload in xss_payloads[:2]:
            query_input = page.locator('[data-testid="rag-query-input"]')
            query_input.fill(payload)
            
            # Check display
            query_display = page.locator('[data-testid="current-query-display"]')
            if query_display.is_visible():
                assert "<script>" not in query_display.text_content()
            
            query_input.clear()
    
    @pytest.mark.e2e
    @pytest.mark.security
    def test_sql_injection_prevention(
        self,
        page: Page,
        api_client,
        security_test_payloads,
        web_server
    ):
        """Test SQL injection prevention."""
        sql_payloads = security_test_payloads['sql_injection']
        
        for payload in sql_payloads:
            # Test in search API
            response = api_client.get(
                '/api/documents/search',
                params={'q': payload}
            )
            
            # Should return valid response, not SQL error
            assert response.status_code in [200, 400]
            if response.json_data:
                # Check for SQL error messages in response
                response_text = json.dumps(response.json_data).lower()
                assert "sql" not in response_text
                assert "syntax error" not in response_text
                assert "table" not in response_text
            
            # Test in authentication
            auth_response = api_client.post(
                '/api/auth/login',
                json={
                    'username': payload,
                    'password': 'test123'
                }
            )
            
            # Should fail gracefully
            assert auth_response.status_code in [400, 401]
            
            # Test in document metadata update
            update_response = api_client.patch(
                '/api/documents/1',
                json={
                    'title': payload,
                    'description': 'Test description'
                }
            )
            
            # Should handle safely
            assert update_response.status_code in [200, 400, 401, 404]
    
    @pytest.mark.e2e
    @pytest.mark.security
    def test_path_traversal_prevention(
        self,
        page: Page,
        api_client,
        security_test_payloads,
        web_server
    ):
        """Test path traversal attack prevention."""
        path_payloads = security_test_payloads['path_traversal']
        
        for payload in path_payloads:
            # Test in file download API
            download_response = api_client.get(
                f'/api/documents/download/{payload}'
            )
            
            # Should not allow access to system files
            assert download_response.status_code in [400, 404]
            
            # Test in file upload with malicious filename
            test_file = Path("test_safe.pdf")
            test_file.write_bytes(b"%PDF-1.4\nTest")
            
            try:
                upload_response = api_client.upload_file(
                    '/api/documents/upload',
                    test_file,
                    additional_data={'filename': payload}
                )
                
                # Should sanitize filename
                if upload_response.success:
                    uploaded_name = upload_response.data.get('filename')
                    assert '..' not in uploaded_name
                    assert '/' not in uploaded_name
                    assert '\\' not in uploaded_name
            finally:
                test_file.unlink()
            
            # Test in API endpoints
            api_response = api_client.get(f'/api/documents/{payload}')
            assert api_response.status_code in [400, 404]
    
    @pytest.mark.e2e
    @pytest.mark.security
    def test_authentication_security(
        self,
        page: Page,
        api_client,
        web_server
    ):
        """Test authentication security measures."""
        # Test 1: Brute force protection
        failed_attempts = []
        for i in range(10):
            response = api_client.post(
                '/api/auth/login',
                json={
                    'username': 'testuser',
                    'password': f'wrong_password_{i}'
                }
            )
            failed_attempts.append(response)
        
        # After multiple failed attempts, should be rate limited or locked
        last_responses = failed_attempts[-3:]
        rate_limited = any(r.status_code == 429 for r in last_responses)
        account_locked = any(
            r.json_data and 'locked' in str(r.json_data).lower()
            for r in last_responses
        )
        
        assert rate_limited or account_locked, "No brute force protection detected"
        
        # Test 2: Session security
        # Login successfully
        login_response = api_client.post(
            '/api/auth/login',
            json={
                'username': 'admin_test',
                'password': 'Admin123!@#'
            }
        )
        
        if login_response.success:
            token = login_response.data.get('token')
            
            # Verify token format (should be secure random)
            assert len(token) >= 32
            assert not token.isdigit()  # Not just numbers
            assert not token.isalpha()  # Not just letters
            
            # Test token expiration
            api_client.auth_token = token
            
            # Should work initially
            profile_response = api_client.get('/api/auth/profile')
            assert profile_response.success
        
        # Test 3: Password requirements
        weak_passwords = [
            '123456',
            'password',
            'admin',
            'test',
            '12345678',
            'qwerty'
        ]
        
        for weak_pass in weak_passwords:
            register_response = api_client.post(
                '/api/auth/register',
                json={
                    'username': f'user_{time.time()}',
                    'email': f'user_{time.time()}@test.com',
                    'password': weak_pass
                }
            )
            
            # Should reject weak passwords
            assert not register_response.success
            if register_response.json_data:
                error_msg = str(register_response.json_data).lower()
                assert any(word in error_msg for word in ['weak', 'strong', 'length', 'complex'])
    
    @pytest.mark.e2e
    @pytest.mark.security
    def test_authorization_and_access_control(
        self,
        page: Page,
        api_client,
        test_user_data,
        web_server
    ):
        """Test authorization and access control."""
        # Create different user sessions
        regular_client = APIClient(web_server)
        admin_client = APIClient(web_server)
        guest_client = APIClient(web_server)
        
        # Authenticate users
        regular_client.authenticate(
            test_user_data['regular']['username'],
            test_user_data['regular']['password']
        )
        
        admin_client.authenticate(
            test_user_data['admin']['username'],
            test_user_data['admin']['password']
        )
        
        # Guest doesn't authenticate
        
        # Test 1: Document access control
        # Admin creates a document
        admin_doc_response = admin_client.post(
            '/api/documents',
            json={'title': 'Admin Document', 'content': 'Sensitive'}
        )
        
        if admin_doc_response.success:
            doc_id = admin_doc_response.data.get('id')
            
            # Regular user shouldn't modify admin's document
            regular_update = regular_client.patch(
                f'/api/documents/{doc_id}',
                json={'title': 'Hacked Title'}
            )
            assert regular_update.status_code in [403, 404]
            
            # Guest shouldn't access at all
            guest_access = guest_client.get(f'/api/documents/{doc_id}')
            assert guest_access.status_code in [401, 403]
        
        # Test 2: Admin-only endpoints
        admin_endpoints = [
            '/api/admin/users',
            '/api/admin/settings',
            '/api/admin/logs',
            '/api/admin/database/backup'
        ]
        
        for endpoint in admin_endpoints:
            # Regular user access
            regular_response = regular_client.get(endpoint)
            assert regular_response.status_code == 403
            
            # Guest access
            guest_response = guest_client.get(endpoint)
            assert guest_response.status_code in [401, 403]
            
            # Admin access (should work or return 404 if not implemented)
            admin_response = admin_client.get(endpoint)
            assert admin_response.status_code in [200, 404]
        
        # Test 3: Rate limiting per user role
        # Admins might have higher limits
        for i in range(100):
            admin_client.get('/api/documents')
        
        # Regular users have standard limits
        regular_limited = False
        for i in range(100):
            response = regular_client.get('/api/documents')
            if response.status_code == 429:
                regular_limited = True
                break
        
        # Guests have strictest limits
        guest_limited = False
        for i in range(50):
            response = guest_client.get('/api/documents')
            if response.status_code == 429:
                guest_limited = True
                break
    
    @pytest.mark.e2e
    @pytest.mark.security
    def test_file_upload_security(
        self,
        page: Page,
        api_client,
        web_server
    ):
        """Test file upload security measures."""
        # Test 1: File type validation
        invalid_files = [
            ('malicious.exe', b'MZ\x90\x00'),  # Executable
            ('script.js', b'alert("XSS")'),     # JavaScript
            ('shell.sh', b'#!/bin/bash\nrm -rf /'),  # Shell script
            ('macro.docm', b'PK\x03\x04'),      # Macro-enabled document
        ]
        
        for filename, content in invalid_files:
            test_file = Path(filename)
            test_file.write_bytes(content)
            
            try:
                response = api_client.upload_file(
                    '/api/documents/upload',
                    test_file
                )
                
                # Should reject non-PDF files
                assert not response.success
                assert response.status_code in [400, 415]
            finally:
                test_file.unlink()
        
        # Test 2: File size limits
        large_file = Path("large.pdf")
        # Create a file that appears to be huge (sparse file)
        large_file.write_bytes(b'%PDF-1.4\n' + b'0' * 1024)  # Small actual size
        
        try:
            # Attempt upload with spoofed size header
            response = api_client.post(
                '/api/documents/upload',
                files={'file': ('large.pdf', large_file.read_bytes(), 'application/pdf')},
                headers={'Content-Length': str(100 * 1024 * 1024)}  # 100MB
            )
            
            # Should enforce size limits
            if response.status_code == 413:
                assert True  # Payload too large
            elif response.success:
                # Check if server validated actual size
                uploaded_size = response.data.get('file_size')
                assert uploaded_size < 100 * 1024 * 1024
        finally:
            large_file.unlink()
        
        # Test 3: Filename sanitization
        dangerous_names = [
            '../../../etc/passwd.pdf',
            'file\x00.pdf',  # Null byte
            'file%00.pdf',   # URL encoded null
            '.hidden.pdf',   # Hidden file
            'CON.pdf',       # Windows reserved name
            'file?.pdf',     # Invalid character
            'a' * 300 + '.pdf'  # Very long name
        ]
        
        safe_pdf = Path("safe.pdf")
        safe_pdf.write_bytes(b'%PDF-1.4\nTest')
        
        try:
            for dangerous_name in dangerous_names:
                response = api_client.post(
                    '/api/documents/upload',
                    files={'file': (dangerous_name, safe_pdf.read_bytes(), 'application/pdf')}
                )
                
                if response.success:
                    # Check sanitized filename
                    stored_name = response.data.get('filename')
                    assert '..' not in stored_name
                    assert '\x00' not in stored_name
                    assert len(stored_name) < 255
        finally:
            safe_pdf.unlink()
    
    @pytest.mark.e2e
    @pytest.mark.security
    def test_csrf_protection(
        self,
        page: Page,
        api_client,
        web_server
    ):
        """Test CSRF (Cross-Site Request Forgery) protection."""
        # Login to get session
        login_response = api_client.post(
            '/api/auth/login',
            json={
                'username': 'test_user',
                'password': 'Test123!@#'
            }
        )
        
        if login_response.success:
            # Try to make request without CSRF token
            response = api_client.post(
                '/api/documents',
                json={'title': 'CSRF Test'},
                headers={'X-CSRF-Token': 'invalid_token'}
            )
            
            # Should require valid CSRF token for state-changing operations
            if 'csrf' in str(response.json_data).lower():
                assert response.status_code in [400, 403]
            
            # Get valid CSRF token
            csrf_response = api_client.get('/api/auth/csrf-token')
            if csrf_response.success:
                csrf_token = csrf_response.data.get('token')
                
                # Request with valid token should work
                valid_response = api_client.post(
                    '/api/documents',
                    json={'title': 'Valid CSRF Test'},
                    headers={'X-CSRF-Token': csrf_token}
                )
                
                assert valid_response.status_code in [200, 201]
    
    @pytest.mark.e2e
    @pytest.mark.security
    def test_api_input_validation(
        self,
        api_client,
        security_test_payloads,
        web_server
    ):
        """Test comprehensive input validation on API endpoints."""
        # Test various malicious inputs
        test_cases = [
            # Overflow attempts
            {'title': 'A' * 10000},
            {'page_count': 2**31},
            {'file_size': -1},
            
            # Type confusion
            {'title': ['array', 'not', 'string']},
            {'page_count': 'not_a_number'},
            {'metadata': 'not_an_object'},
            
            # Special characters
            {'title': '\x00\x01\x02'},
            {'description': '```javascript\nalert(1)\n```'},
            
            # Unicode edge cases
            {'title': '���'},
            {'title': '\u202e\u202d'},  # RTL/LTR override
            
            # Command injection attempts
            {'title': '"; rm -rf /; echo "'},
            {'description': '${7*7}'},  # Template injection
            {'filename': '|whoami'},
        ]
        
        for payload in test_cases:
            # Test in document creation
            response = api_client.post(
                '/api/documents',
                json=payload
            )
            
            # Should validate and reject invalid input
            if response.status_code == 400:
                # Good - rejected invalid input
                assert True
            elif response.success:
                # If accepted, verify it was sanitized
                created_data = response.data
                for key, value in payload.items():
                    if key in created_data:
                        stored_value = created_data[key]
                        # Check for sanitization
                        if isinstance(value, str):
                            assert '\x00' not in str(stored_value)
                            assert '${' not in str(stored_value)
    
    @pytest.mark.e2e
    @pytest.mark.security
    @pytest.mark.performance
    def test_ddos_protection(
        self,
        api_client,
        web_server
    ):
        """Test DDoS and rate limiting protection."""
        import asyncio
        import aiohttp
        
        async def make_concurrent_requests(url: str, count: int):
            """Make concurrent requests to test rate limiting."""
            async with aiohttp.ClientSession() as session:
                tasks = []
                for _ in range(count):
                    task = session.get(f"{url}/api/documents")
                    tasks.append(task)
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                status_codes = []
                for response in responses:
                    if not isinstance(response, Exception):
                        status_codes.append(response.status)
                
                return status_codes
        
        # Test rate limiting
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Make 100 concurrent requests
        status_codes = loop.run_until_complete(
            make_concurrent_requests(web_server, 100)
        )
        
        # Should have rate limiting (429 responses)
        rate_limited = sum(1 for code in status_codes if code == 429)
        assert rate_limited > 0, "No rate limiting detected"
        
        # Test request size limits
        huge_payload = {'data': 'X' * (10 * 1024 * 1024)}  # 10MB payload
        
        response = api_client.post(
            '/api/documents',
            json=huge_payload
        )
        
        # Should reject huge payloads
        assert response.status_code in [413, 400]
        
        loop.close()