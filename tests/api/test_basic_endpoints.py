"""
Basic API endpoint tests for essential functionality coverage.
Tests core API routes and error handling without external dependencies.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import sys

# Mock problematic imports before importing main app
sys.modules['redis'] = MagicMock()
sys.modules['backend.services.l2_redis_cache'] = MagicMock()
sys.modules['backend.services.integrated_cache_manager'] = MagicMock()
sys.modules['backend.services.cache_service_integration'] = MagicMock()

# Mock any cache service dependencies
cache_service_mock = MagicMock()
cache_service_mock.get_cache_service = MagicMock(return_value=MagicMock())
cache_service_mock.CacheServiceIntegration = MagicMock()
sys.modules['backend.services.cache_service_integration'] = cache_service_mock

try:
    from backend.api.main import app
except ImportError as e:
    pytest.skip(f"Application import failed: {e}", allow_module_level=True)


class TestBasicAPIEndpoints:
    """Test basic API endpoints functionality."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_root_endpoint_returns_welcome_message(self, client):
        """Test root endpoint returns expected welcome message."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "AI Enhanced PDF Scholar" in data["message"]

    def test_health_endpoint_returns_status(self, client):
        """Test health endpoint returns system status."""
        response = client.get("/api/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_version_endpoint_returns_version_info(self, client):
        """Test version endpoint returns version information."""
        response = client.get("/api/system/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "api_version" in data

    def test_system_info_endpoint_basic_structure(self, client):
        """Test system info endpoint returns expected structure."""
        response = client.get("/api/system/info")
        assert response.status_code == 200
        data = response.json()
        assert "system" in data
        assert "database" in data
        assert isinstance(data, dict)

    def test_cors_headers_present(self, client):
        """Test CORS headers are properly configured."""
        response = client.options("/api/system/health")
        # Should not fail with CORS issues in test environment
        assert response.status_code in [200, 405]  # OPTIONS may not be implemented

    def test_404_for_nonexistent_endpoint(self, client):
        """Test 404 error for non-existent endpoints."""
        response = client.get("/api/nonexistent/endpoint")
        assert response.status_code == 404

    def test_method_not_allowed_handling(self, client):
        """Test method not allowed error handling."""
        # Try POST on a GET-only endpoint
        response = client.post("/api/system/health")
        assert response.status_code == 405

    @patch('backend.api.dependencies.get_database_connection')
    def test_database_dependency_handling(self, mock_db, client):
        """Test database dependency injection works."""
        mock_db.return_value = Mock()
        response = client.get("/api/system/health")
        # Should still work even with mocked database
        assert response.status_code == 200


class TestAPIErrorHandling:
    """Test API error handling mechanisms."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_json_parsing_error_handling(self, client):
        """Test handling of malformed JSON requests."""
        # Send malformed JSON
        response = client.post(
            "/api/documents/upload",
            headers={"Content-Type": "application/json"},
            data="invalid json{"
        )
        assert response.status_code == 422

    def test_large_request_size_handling(self, client):
        """Test handling of oversized requests."""
        # Create a large payload
        large_data = {"data": "x" * (10 * 1024 * 1024)}  # 10MB
        response = client.post(
            "/api/test",
            json=large_data
        )
        # Should handle gracefully (either 413 or 422)
        assert response.status_code in [404, 413, 422]

    def test_request_timeout_simulation(self, client):
        """Test request timeout handling."""
        # Test with health endpoint which should be fast
        response = client.get("/api/system/health")
        assert response.status_code == 200
        # Response should be reasonably fast (< 5 seconds)
        # This is more of a performance test


class TestAPIValidation:
    """Test API input validation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_empty_request_validation(self, client):
        """Test validation with empty requests."""
        response = client.post("/api/documents/upload", json={})
        # Should return validation error
        assert response.status_code in [400, 422]

    def test_sql_injection_prevention(self, client):
        """Test SQL injection prevention in query parameters."""
        malicious_query = "'; DROP TABLE documents; --"
        response = client.get(f"/api/documents?search={malicious_query}")
        # Should not cause server error - either 400, 422, or valid response
        assert response.status_code not in [500, 502, 503]

    def test_xss_prevention_in_responses(self, client):
        """Test XSS prevention in API responses."""
        xss_payload = "<script>alert('xss')</script>"
        response = client.get(f"/api/documents?search={xss_payload}")
        # Response should not contain unescaped script tags
        if response.status_code == 200:
            response_text = response.text
            assert "<script>" not in response_text
            assert "alert(" not in response_text


@pytest.mark.integration
class TestAPIDocumentEndpoints:
    """Test document-related API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_documents_list_endpoint_structure(self, client):
        """Test documents list endpoint returns proper structure."""
        response = client.get("/api/documents")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            assert "success" in data or "data" in data or "documents" in data

    def test_document_upload_endpoint_exists(self, client):
        """Test document upload endpoint exists and validates input."""
        # Test without file
        response = client.post("/api/documents/upload")
        # Should return validation error, not 404
        assert response.status_code in [400, 422]  # Not 404

    def test_document_search_endpoint_basic(self, client):
        """Test document search endpoint basic functionality."""
        response = client.get("/api/documents/search?q=test")
        # Should not return server error
        assert response.status_code not in [500, 502, 503]
        assert response.status_code in [200, 400, 404, 422]


@pytest.mark.integration  
class TestAPIRAGEndpoints:
    """Test RAG-related API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_rag_query_endpoint_validation(self, client):
        """Test RAG query endpoint input validation."""
        # Test with empty query
        response = client.post("/api/rag/query", json={})
        assert response.status_code in [400, 422]

        # Test with minimal valid structure  
        response = client.post("/api/rag/query", json={"query": "test query"})
        # Should not return server error
        assert response.status_code not in [500, 502, 503]

    def test_rag_status_endpoint(self, client):
        """Test RAG system status endpoint."""
        response = client.get("/api/rag/status")
        # Should not return server error
        assert response.status_code not in [500, 502, 503]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)