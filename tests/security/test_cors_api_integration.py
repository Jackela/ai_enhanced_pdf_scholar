"""
CORS API Integration Tests

Tests CORS security integration with actual API endpoints.
Verifies that CORS policies are properly enforced on real application endpoints.
"""

import pytest
import os
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

# Import the actual main app
from backend.api.main import app


class TestCORSAPIIntegration:
    """Test CORS integration with actual API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client for the actual FastAPI app."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock all dependencies to focus on CORS testing."""
        with patch('backend.api.dependencies.get_db') as mock_get_db, \
             patch('backend.api.dependencies.get_enhanced_rag') as mock_get_rag, \
             patch('backend.api.dependencies.get_library_controller') as mock_get_controller:
            
            # Mock database
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            # Mock RAG service
            mock_rag = Mock()
            mock_get_rag.return_value = mock_rag
            
            # Mock controller
            mock_controller = Mock()
            mock_controller.get_documents.return_value = []
            mock_controller.get_document_stats.return_value = {"total": 0, "indexed": 0}
            mock_get_controller.return_value = mock_controller
            
            yield {
                'db': mock_db,
                'rag': mock_rag,
                'controller': mock_controller
            }
    
    def test_development_cors_allows_localhost(self, client, mock_dependencies):
        """Test that development CORS allows localhost origins."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000,http://localhost:8000"
        }):
            # Test a real API endpoint
            response = client.get("/api/system/health", headers={
                "Origin": "http://localhost:3000"
            })
            
            assert response.status_code == 200
            assert "Access-Control-Allow-Origin" in response.headers
            assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    
    def test_production_cors_blocks_localhost(self, client, mock_dependencies):
        """Test that production CORS blocks localhost origins."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            response = client.get("/api/system/health", headers={
                "Origin": "http://localhost:3000"
            })
            
            assert response.status_code == 200
            # Localhost should not be allowed in production
            assert "Access-Control-Allow-Origin" not in response.headers or \
                   response.headers.get("Access-Control-Allow-Origin") != "http://localhost:3000"
    
    def test_cors_preflight_document_api(self, client, mock_dependencies):
        """Test CORS preflight for document API endpoints."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            # Send preflight request for document upload
            response = client.options("/api/documents/", headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,Authorization"
            })
            
            assert response.status_code == 200
            assert "Access-Control-Allow-Origin" in response.headers
            assert "Access-Control-Allow-Methods" in response.headers
            assert "POST" in response.headers["Access-Control-Allow-Methods"]
    
    def test_cors_rag_api_endpoints(self, client, mock_dependencies):
        """Test CORS on RAG API endpoints."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            # Mock RAG service response
            mock_dependencies['controller'].query_document.return_value = {
                "response": "Test response",
                "sources": []
            }
            
            response = client.post("/api/rag/query", 
                json={"query": "test query", "document_id": 1},
                headers={"Origin": "http://localhost:3000"}
            )
            
            # Should allow the request
            assert "Access-Control-Allow-Origin" in response.headers
            assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    
    def test_cors_library_api_endpoints(self, client, mock_dependencies):
        """Test CORS on library API endpoints."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            response = client.get("/api/library/stats", headers={
                "Origin": "http://localhost:3000"
            })
            
            assert "Access-Control-Allow-Origin" in response.headers
            assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    
    def test_cors_websocket_origin_validation(self, client, mock_dependencies):
        """Test CORS-like behavior for WebSocket connections."""
        # Note: WebSocket CORS is handled differently, but we can test origin header
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            # Test WebSocket endpoint (this will fail to upgrade but we can see the response)
            response = client.get("/ws/test-client", headers={
                "Origin": "http://localhost:3000",
                "Connection": "upgrade",
                "Upgrade": "websocket"
            })
            
            # WebSocket upgrade will fail in test client, but endpoint should exist
            # This test mainly verifies the endpoint is accessible
            assert response.status_code in [426, 400]  # Upgrade required or bad request
    
    def test_multiple_allowed_origins(self, client, mock_dependencies):
        """Test that multiple allowed origins work correctly."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development", 
            "CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000,https://staging.example.com"
        }):
            origins_to_test = [
                "http://localhost:3000",
                "http://127.0.0.1:3000", 
                "https://staging.example.com"
            ]
            
            for origin in origins_to_test:
                response = client.get("/api/system/health", headers={
                    "Origin": origin
                })
                
                assert response.status_code == 200
                assert "Access-Control-Allow-Origin" in response.headers
                assert response.headers["Access-Control-Allow-Origin"] == origin
    
    def test_blocked_origin_no_cors_headers(self, client, mock_dependencies):
        """Test that blocked origins don't get CORS headers."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            response = client.get("/api/system/health", headers={
                "Origin": "https://malicious.com"
            })
            
            assert response.status_code == 200
            # Blocked origin should not get CORS headers
            assert "Access-Control-Allow-Origin" not in response.headers
    
    def test_cors_headers_content_security(self, client, mock_dependencies):
        """Test that CORS headers don't leak sensitive information."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            response = client.get("/api/system/health", headers={
                "Origin": "https://app.example.com"
            })
            
            # Check that only expected CORS headers are present
            cors_headers = [
                header for header in response.headers.keys() 
                if header.lower().startswith("access-control-")
            ]
            
            expected_headers = [
                "Access-Control-Allow-Origin",
                "Access-Control-Allow-Credentials"
            ]
            
            for expected in expected_headers:
                assert expected in cors_headers
            
            # Ensure no unexpected headers that might leak info
            assert "Access-Control-Expose-Headers" in response.headers
            exposed_headers = response.headers["Access-Control-Expose-Headers"]
            # Should not expose sensitive internal headers
            assert "Authorization" not in exposed_headers
            assert "Set-Cookie" not in exposed_headers
    
    def test_cors_method_restrictions(self, client, mock_dependencies):
        """Test that CORS method restrictions work properly."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "testing",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            # Testing environment should be more restrictive
            response = client.options("/api/documents/", headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            })
            
            assert response.status_code == 200
            allowed_methods = response.headers.get("Access-Control-Allow-Methods", "")
            
            # Testing environment should have limited methods
            assert "GET" in allowed_methods
            assert "POST" in allowed_methods
            # Should not include all possible methods like PATCH, etc.
    
    def test_cors_credentials_environment_specific(self, client, mock_dependencies):
        """Test that credential handling varies by environment."""
        # Development should allow credentials
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            response = client.get("/api/system/health", headers={
                "Origin": "http://localhost:3000"
            })
            
            assert "Access-Control-Allow-Credentials" in response.headers
            assert response.headers["Access-Control-Allow-Credentials"] == "true"
        
        # Testing should not allow credentials
        with patch.dict(os.environ, {
            "ENVIRONMENT": "testing",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            response = client.get("/api/system/health", headers={
                "Origin": "http://localhost:3000"
            })
            
            # Testing environment should not send credentials header or should be false
            credentials_header = response.headers.get("Access-Control-Allow-Credentials")
            assert credentials_header != "true"


class TestCORSSecurityVulnerabilities:
    """Test protection against CORS-based security vulnerabilities."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock dependencies."""
        with patch('backend.api.dependencies.get_db') as mock_get_db, \
             patch('backend.api.dependencies.get_enhanced_rag') as mock_get_rag, \
             patch('backend.api.dependencies.get_library_controller') as mock_get_controller:
            
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            mock_rag = Mock()
            mock_get_rag.return_value = mock_rag
            
            mock_controller = Mock()
            mock_controller.get_documents.return_value = []
            mock_get_controller.return_value = mock_controller
            
            yield
    
    def test_origin_reflection_attack_protection(self, client, mock_dependencies):
        """Test protection against origin reflection attacks."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            # Attempt origin reflection attack
            malicious_origin = "https://evil.com"
            response = client.get("/api/system/health", headers={
                "Origin": malicious_origin
            })
            
            # Should not reflect the malicious origin
            cors_origin = response.headers.get("Access-Control-Allow-Origin")
            assert cors_origin != malicious_origin
            assert cors_origin != "*"  # Should not be wildcard either
    
    def test_subdomain_confusion_protection(self, client, mock_dependencies):
        """Test protection against subdomain confusion attacks."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            # Attempt with confusing subdomain
            response = client.get("/api/system/health", headers={
                "Origin": "https://app.example.com.evil.com"
            })
            
            # Should not allow the confusing subdomain
            assert response.headers.get("Access-Control-Allow-Origin") != "https://app.example.com.evil.com"
    
    def test_protocol_confusion_protection(self, client, mock_dependencies):
        """Test protection against protocol confusion."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            # Attempt with different protocol
            response = client.get("/api/system/health", headers={
                "Origin": "http://app.example.com"  # HTTP instead of HTTPS
            })
            
            # Should not allow different protocol
            assert response.headers.get("Access-Control-Allow-Origin") != "http://app.example.com"
    
    def test_port_confusion_protection(self, client, mock_dependencies):
        """Test protection against port confusion."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com:443"
        }):
            # Attempt with different port
            response = client.get("/api/system/health", headers={
                "Origin": "https://app.example.com:8443"
            })
            
            # Should not allow different port
            assert response.headers.get("Access-Control-Allow-Origin") != "https://app.example.com:8443"
    
    def test_null_origin_handling(self, client, mock_dependencies):
        """Test handling of null origin."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            # Some browsers send null origin in certain cases
            response = client.get("/api/system/health", headers={
                "Origin": "null"
            })
            
            # Should not allow null origin
            assert response.headers.get("Access-Control-Allow-Origin") != "null"
    
    def test_case_sensitivity_security(self, client, mock_dependencies):
        """Test that case sensitivity is maintained for security."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            # Attempt with different casing
            response = client.get("/api/system/health", headers={
                "Origin": "https://APP.EXAMPLE.COM"
            })
            
            # Should not allow different casing (case sensitive)
            assert response.headers.get("Access-Control-Allow-Origin") != "https://APP.EXAMPLE.COM"


class TestCORSPerformanceAndResilience:
    """Test CORS configuration performance and resilience."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_cors_config_caching(self):
        """Test that CORS config is efficiently cached/reused."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            from backend.api.cors_config import get_cors_config
            
            # Multiple calls should be efficient
            config1 = get_cors_config()
            config2 = get_cors_config()
            
            # Should have same configuration
            assert config1.get_middleware_config() == config2.get_middleware_config()
    
    def test_many_origins_performance(self, client):
        """Test performance with many allowed origins."""
        # Create many origins
        origins = [f"https://app{i}.example.com" for i in range(50)]
        
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": ",".join(origins)
        }) and patch('backend.api.dependencies.get_db'), \
             patch('backend.api.dependencies.get_enhanced_rag'), \
             patch('backend.api.dependencies.get_library_controller'):
            
            # Test that it still works with many origins
            response = client.get("/api/system/health", headers={
                "Origin": origins[25]  # Test middle origin
            })
            
            assert response.status_code == 200
            assert response.headers.get("Access-Control-Allow-Origin") == origins[25]
    
    def test_malformed_cors_origins_resilience(self):
        """Test resilience against malformed CORS origins configuration."""
        malformed_configs = [
            "http://localhost:3000,,https://example.com",  # Extra comma
            " http://localhost:3000 , https://example.com ",  # Extra spaces
            "http://localhost:3000,",  # Trailing comma
        ]
        
        for config in malformed_configs:
            with patch.dict(os.environ, {
                "ENVIRONMENT": "development",
                "CORS_ORIGINS": config
            }):
                from backend.api.cors_config import CORSConfig
                cors_config = CORSConfig()
                
                # Should handle malformed config gracefully
                origins = cors_config.get_middleware_config()["allow_origins"]
                assert "http://localhost:3000" in origins
                assert "https://example.com" in origins
                assert "" not in origins  # Empty strings should be filtered out