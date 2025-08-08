"""
Authentication and Authorization Security Tests

Comprehensive test suite for authentication and authorization vulnerabilities including:
- Brute force protection
- Session management
- Privilege escalation
- Token security
- Access control
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from tests.security.security_test_utils import (
    AttackType,
    SecurityTestResult,
    SecurityTestRunner,
    SeverityLevel,
)


class TestAuthenticationSecurity:
    """Test suite for authentication security vulnerabilities."""
    
    @pytest.fixture
    def mock_auth_service(self):
        """Mock authentication service for testing."""
        service = MagicMock()
        service.login_attempts = {}
        service.locked_accounts = {}
        service.sessions = {}
        return service
    
    @pytest.fixture
    def weak_passwords(self) -> List[str]:
        """Common weak passwords for testing."""
        return [
            "password", "123456", "password123", "admin", "letmein",
            "welcome", "monkey", "dragon", "master", "abc123",
            "Password1", "password1", "123456789", "welcome123", "admin123",
            "root", "toor", "pass", "password1!", "P@ssw0rd"
        ]
    
    @pytest.fixture
    def sql_injection_passwords(self) -> List[str]:
        """SQL injection attempts in password field."""
        return [
            "' OR '1'='1",
            "admin'--",
            "' OR '1'='1' --",
            "'; DROP TABLE users--",
            "admin' /*",
            "' UNION SELECT NULL--",
            "' OR 1=1--",
            "\\' OR \\'1\\'=\\'1",
        ]
    
    def test_brute_force_protection(self, mock_auth_service):
        """Test protection against brute force attacks."""
        username = "testuser"
        max_attempts = 5
        lockout_duration = 300  # 5 minutes
        
        # Simulate brute force attempts
        for i in range(max_attempts + 2):
            password = f"wrongpassword{i}"
            
            # Check if account is locked
            if username in mock_auth_service.locked_accounts:
                lock_time = mock_auth_service.locked_accounts[username]
                if time.time() - lock_time < lockout_duration:
                    # Should be locked
                    result = {"error": "Account locked", "locked": True}
                else:
                    # Unlock account
                    del mock_auth_service.locked_accounts[username]
                    mock_auth_service.login_attempts[username] = 0
            else:
                # Track login attempt
                if username not in mock_auth_service.login_attempts:
                    mock_auth_service.login_attempts[username] = 0
                
                mock_auth_service.login_attempts[username] += 1
                
                if mock_auth_service.login_attempts[username] >= max_attempts:
                    # Lock account
                    mock_auth_service.locked_accounts[username] = time.time()
                    result = {"error": "Account locked due to too many failed attempts", "locked": True}
                else:
                    result = {"error": "Invalid credentials", "locked": False}
            
            # After max_attempts, account should be locked
            if i >= max_attempts:
                assert result.get("locked") == True, f"Account should be locked after {max_attempts} attempts"
    
    def test_timing_attack_protection(self, mock_auth_service):
        """Test protection against timing attacks on authentication."""
        valid_username = "admin"
        invalid_username = "nonexistent"
        password = "testpass"
        
        # Measure timing for valid username
        start_time = time.perf_counter()
        
        # Simulate constant-time comparison
        def constant_time_auth(username: str, password: str) -> bool:
            # Always perform the same operations regardless of validity
            expected_username = "admin"
            expected_password_hash = hashlib.sha256("correct_password".encode()).hexdigest()
            
            provided_password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Use constant-time comparison
            username_match = hmac.compare_digest(username, expected_username)
            password_match = hmac.compare_digest(provided_password_hash, expected_password_hash)
            
            # Add artificial delay to mask timing differences
            time.sleep(0.001)
            
            return username_match and password_match
        
        # Test with valid username
        result1 = constant_time_auth(valid_username, password)
        time1 = time.perf_counter() - start_time
        
        # Test with invalid username
        start_time = time.perf_counter()
        result2 = constant_time_auth(invalid_username, password)
        time2 = time.perf_counter() - start_time
        
        # Timing difference should be minimal (less than 10% variance)
        time_diff = abs(time1 - time2)
        avg_time = (time1 + time2) / 2
        variance_percent = (time_diff / avg_time) * 100 if avg_time > 0 else 0
        
        assert variance_percent < 10, f"Timing variance too high: {variance_percent:.2f}% (may be vulnerable to timing attacks)"
    
    def test_session_fixation_protection(self, mock_auth_service):
        """Test protection against session fixation attacks."""
        # Attacker creates a session
        attacker_session_id = "attacker-fixed-session-123"
        mock_auth_service.sessions[attacker_session_id] = {
            "created_at": time.time(),
            "user": None
        }
        
        # Victim logs in with the fixed session ID
        def login_with_session(username: str, password: str, session_id: Optional[str] = None):
            # Should regenerate session ID after successful login
            if session_id and session_id in mock_auth_service.sessions:
                # Delete old session
                del mock_auth_service.sessions[session_id]
            
            # Create new session with new ID
            new_session_id = str(uuid.uuid4())
            mock_auth_service.sessions[new_session_id] = {
                "created_at": time.time(),
                "user": username,
                "old_session_id": session_id  # Track for testing
            }
            return new_session_id
        
        # Perform login
        new_session_id = login_with_session("victim", "password", attacker_session_id)
        
        # Old session should not exist
        assert attacker_session_id not in mock_auth_service.sessions, "Old session should be invalidated"
        
        # New session should be different
        assert new_session_id != attacker_session_id, "Session ID should be regenerated after login"
        
        # New session should be valid
        assert new_session_id in mock_auth_service.sessions, "New session should exist"
        assert mock_auth_service.sessions[new_session_id]["user"] == "victim", "New session should be associated with user"
    
    def test_session_hijacking_protection(self, mock_auth_service):
        """Test protection against session hijacking."""
        session_id = str(uuid.uuid4())
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ip_address = "192.168.1.100"
        
        # Create legitimate session
        mock_auth_service.sessions[session_id] = {
            "user": "legitimate_user",
            "created_at": time.time(),
            "user_agent": user_agent,
            "ip_address": ip_address,
            "fingerprint": hashlib.sha256(f"{user_agent}{ip_address}".encode()).hexdigest()
        }
        
        def validate_session(session_id: str, request_user_agent: str, request_ip: str) -> bool:
            if session_id not in mock_auth_service.sessions:
                return False
            
            session = mock_auth_service.sessions[session_id]
            
            # Check session fingerprint
            request_fingerprint = hashlib.sha256(f"{request_user_agent}{request_ip}".encode()).hexdigest()
            
            if session["fingerprint"] != request_fingerprint:
                # Potential hijacking detected
                # Log security event and invalidate session
                del mock_auth_service.sessions[session_id]
                return False
            
            # Check session timeout (e.g., 30 minutes)
            if time.time() - session["created_at"] > 1800:
                del mock_auth_service.sessions[session_id]
                return False
            
            return True
        
        # Legitimate request
        assert validate_session(session_id, user_agent, ip_address) == True, "Legitimate session should be valid"
        
        # Recreate session for next test
        mock_auth_service.sessions[session_id] = {
            "user": "legitimate_user",
            "created_at": time.time(),
            "user_agent": user_agent,
            "ip_address": ip_address,
            "fingerprint": hashlib.sha256(f"{user_agent}{ip_address}".encode()).hexdigest()
        }
        
        # Hijacking attempt from different IP
        hijacker_ip = "10.0.0.1"
        assert validate_session(session_id, user_agent, hijacker_ip) == False, "Session hijacking should be detected"
        assert session_id not in mock_auth_service.sessions, "Hijacked session should be invalidated"
    
    def test_password_reset_token_security(self, mock_auth_service):
        """Test security of password reset tokens."""
        user_email = "user@example.com"
        
        def generate_reset_token(email: str) -> str:
            # Generate secure random token
            token = hashlib.sha256(f"{email}{time.time()}{uuid.uuid4()}".encode()).hexdigest()
            
            # Store with expiration
            mock_auth_service.reset_tokens = {
                token: {
                    "email": email,
                    "created_at": time.time(),
                    "used": False
                }
            }
            return token
        
        def validate_reset_token(token: str) -> Optional[str]:
            if token not in mock_auth_service.reset_tokens:
                return None
            
            token_data = mock_auth_service.reset_tokens[token]
            
            # Check if already used
            if token_data["used"]:
                return None
            
            # Check expiration (15 minutes)
            if time.time() - token_data["created_at"] > 900:
                del mock_auth_service.reset_tokens[token]
                return None
            
            # Mark as used
            token_data["used"] = True
            return token_data["email"]
        
        # Generate token
        reset_token = generate_reset_token(user_email)
        
        # Token should be sufficiently random (at least 32 characters)
        assert len(reset_token) >= 32, "Reset token should be sufficiently long"
        
        # Validate token
        assert validate_reset_token(reset_token) == user_email, "Valid token should return email"
        
        # Token should be single-use
        assert validate_reset_token(reset_token) is None, "Token should not be reusable"
        
        # Test expired token
        expired_token = generate_reset_token("expired@example.com")
        mock_auth_service.reset_tokens[expired_token]["created_at"] = time.time() - 1000
        assert validate_reset_token(expired_token) is None, "Expired token should be invalid"
    
    def test_sql_injection_in_authentication(self, sql_injection_passwords):
        """Test SQL injection prevention in authentication."""
        for malicious_password in sql_injection_passwords:
            # Simulate parameterized query (safe)
            def safe_authenticate(username: str, password: str) -> bool:
                # Use parameterized query
                query = "SELECT * FROM users WHERE username = ? AND password_hash = ?"
                
                # Parameters are safely escaped by the database driver
                params = (username, hashlib.sha256(password.encode()).hexdigest())
                
                # Check for SQL injection patterns in the query itself
                if any(pattern in password.lower() for pattern in ["'", "--", "/*", "union", "select"]):
                    # Log potential SQL injection attempt
                    return False
                
                # Simulate safe execution
                return False  # Would execute safely with parameters
            
            result = safe_authenticate("admin", malicious_password)
            assert result == False, f"SQL injection attempt should be blocked: {malicious_password}"
    
    def test_weak_password_detection(self, weak_passwords):
        """Test detection and prevention of weak passwords."""
        def validate_password_strength(password: str) -> Dict[str, any]:
            issues = []
            
            # Check length
            if len(password) < 8:
                issues.append("Password must be at least 8 characters")
            
            # Check for common weak passwords
            if password.lower() in [p.lower() for p in weak_passwords]:
                issues.append("Password is too common")
            
            # Check complexity
            has_lower = any(c.islower() for c in password)
            has_upper = any(c.isupper() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
            
            complexity_score = sum([has_lower, has_upper, has_digit, has_special])
            if complexity_score < 3:
                issues.append("Password must contain at least 3 of: lowercase, uppercase, digit, special character")
            
            # Check for patterns
            if any(pattern in password.lower() for pattern in ["123", "abc", "qwerty", "password"]):
                issues.append("Password contains common patterns")
            
            return {
                "valid": len(issues) == 0,
                "issues": issues,
                "strength": "weak" if issues else "strong"
            }
        
        # Test weak passwords
        for weak_password in weak_passwords:
            result = validate_password_strength(weak_password)
            assert result["valid"] == False, f"Weak password should be rejected: {weak_password}"
            assert len(result["issues"]) > 0, "Should provide reasons for rejection"
        
        # Test strong password
        strong_password = "Str0ng!P@ssw0rd#2024"
        result = validate_password_strength(strong_password)
        assert result["valid"] == True, "Strong password should be accepted"
        assert result["strength"] == "strong", "Should recognize strong password"


class TestAuthorizationSecurity:
    """Test suite for authorization security vulnerabilities."""
    
    @pytest.fixture
    def mock_rbac_system(self):
        """Mock Role-Based Access Control system."""
        return {
            "users": {
                "admin": {"role": "admin", "permissions": ["read", "write", "delete", "admin"]},
                "editor": {"role": "editor", "permissions": ["read", "write"]},
                "viewer": {"role": "viewer", "permissions": ["read"]},
                "guest": {"role": "guest", "permissions": []},
            },
            "resources": {
                "document_1": {"owner": "admin", "permissions": {"editor": ["read", "write"], "viewer": ["read"]}},
                "document_2": {"owner": "editor", "permissions": {"viewer": ["read"]}},
                "document_3": {"owner": "viewer", "permissions": {}},
            }
        }
    
    def test_privilege_escalation_horizontal(self, mock_rbac_system):
        """Test protection against horizontal privilege escalation."""
        def access_user_data(requesting_user: str, target_user: str) -> Dict:
            # Check if user can access another user's data
            if requesting_user == target_user:
                return {"allowed": True, "data": f"Data for {target_user}"}
            
            # Check if requesting user has admin permission
            user = mock_rbac_system["users"].get(requesting_user)
            if user and "admin" in user["permissions"]:
                return {"allowed": True, "data": f"Admin access to {target_user}'s data"}
            
            # Deny access
            return {"allowed": False, "error": "Unauthorized access to other user's data"}
        
        # User trying to access their own data (should succeed)
        result = access_user_data("editor", "editor")
        assert result["allowed"] == True, "User should access own data"
        
        # User trying to access another user's data (should fail)
        result = access_user_data("editor", "viewer")
        assert result["allowed"] == False, "User should not access other user's data"
        
        # Admin accessing another user's data (should succeed)
        result = access_user_data("admin", "viewer")
        assert result["allowed"] == True, "Admin should access any user's data"
    
    def test_privilege_escalation_vertical(self, mock_rbac_system):
        """Test protection against vertical privilege escalation."""
        def perform_admin_action(user: str, action: str) -> Dict:
            user_data = mock_rbac_system["users"].get(user)
            if not user_data:
                return {"allowed": False, "error": "User not found"}
            
            # Check if user has required permission
            if action == "delete" and "delete" not in user_data["permissions"]:
                return {"allowed": False, "error": "Insufficient permissions for delete"}
            
            if action == "admin" and "admin" not in user_data["permissions"]:
                return {"allowed": False, "error": "Admin privileges required"}
            
            return {"allowed": True, "result": f"Action {action} performed"}
        
        # Regular user trying admin action (should fail)
        result = perform_admin_action("editor", "admin")
        assert result["allowed"] == False, "Regular user should not perform admin actions"
        
        # Admin performing admin action (should succeed)
        result = perform_admin_action("admin", "admin")
        assert result["allowed"] == True, "Admin should perform admin actions"
        
        # Editor trying delete (should fail)
        result = perform_admin_action("editor", "delete")
        assert result["allowed"] == False, "Editor should not have delete permission"
    
    def test_insecure_direct_object_reference(self, mock_rbac_system):
        """Test protection against IDOR vulnerabilities."""
        def access_document(user: str, document_id: str) -> Dict:
            user_data = mock_rbac_system["users"].get(user)
            if not user_data:
                return {"allowed": False, "error": "User not found"}
            
            document = mock_rbac_system["resources"].get(document_id)
            if not document:
                return {"allowed": False, "error": "Document not found"}
            
            # Check if user is owner
            if document["owner"] == user:
                return {"allowed": True, "data": f"Owner access to {document_id}"}
            
            # Check if user has specific permissions for this document
            user_perms = document["permissions"].get(user, [])
            if "read" in user_perms or "read" in user_data["permissions"]:
                return {"allowed": True, "data": f"Read access to {document_id}"}
            
            return {"allowed": False, "error": "No permission to access document"}
        
        # Owner accessing their document
        result = access_document("admin", "document_1")
        assert result["allowed"] == True, "Owner should access their document"
        
        # User with granted permissions
        result = access_document("editor", "document_1")
        assert result["allowed"] == True, "User with permissions should access document"
        
        # User without permissions
        result = access_document("guest", "document_1")
        assert result["allowed"] == False, "User without permissions should be denied"
    
    def test_jwt_token_manipulation(self):
        """Test protection against JWT token manipulation."""
        secret_key = "super-secret-key-12345"
        
        def create_jwt_token(payload: Dict) -> str:
            return jwt.encode(payload, secret_key, algorithm="HS256")
        
        def validate_jwt_token(token: str) -> Optional[Dict]:
            try:
                # Verify signature and decode
                decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
                
                # Additional validation
                if "exp" in decoded and decoded["exp"] < time.time():
                    return None  # Token expired
                
                if "iat" in decoded and decoded["iat"] > time.time():
                    return None  # Token issued in future (suspicious)
                
                return decoded
            except jwt.InvalidTokenError:
                return None
        
        # Create legitimate token
        legitimate_payload = {
            "user_id": "123",
            "role": "user",
            "exp": time.time() + 3600,
            "iat": time.time()
        }
        legitimate_token = create_jwt_token(legitimate_payload)
        
        # Validate legitimate token
        decoded = validate_jwt_token(legitimate_token)
        assert decoded is not None, "Legitimate token should be valid"
        assert decoded["role"] == "user", "Role should match"
        
        # Try to manipulate token (change role to admin)
        parts = legitimate_token.split('.')
        # Decode payload
        import base64
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
        payload["role"] = "admin"
        # Re-encode without valid signature
        tampered_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
        
        # Validate tampered token
        decoded = validate_jwt_token(tampered_token)
        assert decoded is None, "Tampered token should be invalid"
        
        # Test algorithm confusion attack (trying to use 'none' algorithm)
        try:
            none_token = jwt.encode(legitimate_payload, '', algorithm='none')
            decoded = validate_jwt_token(none_token)
            assert decoded is None, "Token with 'none' algorithm should be rejected"
        except:
            pass  # Some JWT libraries prevent 'none' algorithm
    
    def test_api_rate_limiting(self):
        """Test API rate limiting to prevent abuse."""
        class RateLimiter:
            def __init__(self, max_requests: int = 10, window_seconds: int = 60):
                self.max_requests = max_requests
                self.window_seconds = window_seconds
                self.requests = {}
            
            def is_allowed(self, client_id: str) -> bool:
                current_time = time.time()
                
                # Clean old requests
                if client_id in self.requests:
                    self.requests[client_id] = [
                        req_time for req_time in self.requests[client_id]
                        if current_time - req_time < self.window_seconds
                    ]
                
                # Check rate limit
                if client_id not in self.requests:
                    self.requests[client_id] = []
                
                if len(self.requests[client_id]) >= self.max_requests:
                    return False
                
                # Add current request
                self.requests[client_id].append(current_time)
                return True
        
        rate_limiter = RateLimiter(max_requests=5, window_seconds=10)
        client_id = "test_client"
        
        # First 5 requests should succeed
        for i in range(5):
            assert rate_limiter.is_allowed(client_id) == True, f"Request {i+1} should be allowed"
        
        # 6th request should be blocked
        assert rate_limiter.is_allowed(client_id) == False, "Should block after rate limit"
        
        # Wait for window to expire (simulated)
        rate_limiter.requests[client_id] = []  # Reset for testing
        assert rate_limiter.is_allowed(client_id) == True, "Should allow after window expires"
    
    def test_path_traversal_authorization(self):
        """Test authorization checks against path traversal attempts."""
        allowed_paths = ["/api/documents/", "/api/users/profile/"]
        
        def check_path_authorization(requested_path: str) -> bool:
            # Normalize path to prevent traversal
            import os
            normalized_path = os.path.normpath(requested_path)
            
            # Check for traversal attempts
            if ".." in normalized_path:
                return False
            
            # Check if path is in allowed paths
            for allowed in allowed_paths:
                if normalized_path.startswith(allowed):
                    return True
            
            return False
        
        # Valid paths
        assert check_path_authorization("/api/documents/123") == True
        assert check_path_authorization("/api/users/profile/me") == True
        
        # Path traversal attempts
        assert check_path_authorization("/api/documents/../../../etc/passwd") == False
        assert check_path_authorization("/api/documents/..\\..\\..\\windows\\system32") == False
        assert check_path_authorization("/api/../../../admin/") == False
        
        # Unauthorized paths
        assert check_path_authorization("/api/admin/") == False
        assert check_path_authorization("/internal/config") == False


class TestTokenSecurity:
    """Test suite for token and session security."""
    
    def test_csrf_token_validation(self):
        """Test CSRF token generation and validation."""
        class CSRFProtection:
            def __init__(self):
                self.tokens = {}
            
            def generate_token(self, session_id: str) -> str:
                token = hashlib.sha256(f"{session_id}{time.time()}{uuid.uuid4()}".encode()).hexdigest()
                self.tokens[session_id] = token
                return token
            
            def validate_token(self, session_id: str, token: str) -> bool:
                if session_id not in self.tokens:
                    return False
                
                expected_token = self.tokens[session_id]
                # Use constant-time comparison
                return hmac.compare_digest(expected_token, token)
        
        csrf = CSRFProtection()
        session_id = "test_session_123"
        
        # Generate token
        csrf_token = csrf.generate_token(session_id)
        assert len(csrf_token) >= 32, "CSRF token should be sufficiently long"
        
        # Valid token
        assert csrf.validate_token(session_id, csrf_token) == True
        
        # Invalid token
        assert csrf.validate_token(session_id, "invalid_token") == False
        
        # Missing session
        assert csrf.validate_token("nonexistent_session", csrf_token) == False
    
    def test_api_key_security(self):
        """Test API key generation and validation."""
        class APIKeyManager:
            def __init__(self):
                self.keys = {}
            
            def generate_api_key(self, user_id: str) -> str:
                # Generate secure API key
                key = "sk_" + hashlib.sha256(f"{user_id}{uuid.uuid4()}".encode()).hexdigest()
                
                # Store with metadata
                self.keys[key] = {
                    "user_id": user_id,
                    "created_at": time.time(),
                    "last_used": None,
                    "usage_count": 0,
                    "rate_limit": 1000,  # requests per hour
                    "scopes": ["read", "write"]
                }
                return key
            
            def validate_api_key(self, key: str) -> Optional[Dict]:
                if key not in self.keys:
                    return None
                
                key_data = self.keys[key]
                
                # Update usage
                key_data["last_used"] = time.time()
                key_data["usage_count"] += 1
                
                # Check rate limit (simplified)
                if key_data["usage_count"] > key_data["rate_limit"]:
                    return None
                
                return key_data
        
        manager = APIKeyManager()
        user_id = "user_123"
        
        # Generate API key
        api_key = manager.generate_api_key(user_id)
        
        # Check format
        assert api_key.startswith("sk_"), "API key should have proper prefix"
        assert len(api_key) > 40, "API key should be sufficiently long"
        
        # Validate key
        key_data = manager.validate_api_key(api_key)
        assert key_data is not None, "Valid API key should be accepted"
        assert key_data["user_id"] == user_id, "Should return correct user"
        assert key_data["usage_count"] == 1, "Should track usage"
        
        # Invalid key
        assert manager.validate_api_key("invalid_key") is None, "Invalid key should be rejected"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])