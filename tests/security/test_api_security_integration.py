"""
API Security Integration Tests

Test SQL injection prevention at the FastAPI endpoint level,
verifying that malicious requests are properly handled and blocked.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from backend.api.routes.documents import router
from backend.api.models import DocumentQueryParams
from fastapi import FastAPI


class TestAPISecurityIntegration:
    """Integration tests for API-level SQL injection prevention."""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app with document router."""
        test_app = FastAPI()
        test_app.include_router(router, prefix="/documents")
        return test_app
    
    @pytest.fixture
    def client(self, app):
        """Create test client for API requests."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_controller(self):
        """Mock library controller dependency."""
        with patch('backend.api.routes.documents.get_library_controller') as mock:
            mock_controller = Mock()
            mock_controller.get_documents.return_value = []
            mock.return_value = mock_controller
            yield mock_controller

    def test_valid_query_parameters_accepted(self, client, mock_controller):
        """Test that valid query parameters are accepted."""
        # Valid parameters should work
        response = client.get("/documents/", params={
            "search_query": "Machine Learning",
            "sort_by": "title",
            "sort_order": "asc", 
            "page": 1,
            "per_page": 10
        })
        
        # Should succeed (even if mocked)
        # The fact that we don't get a validation error is the test
        assert response.status_code != 422  # Validation error status

    def test_sql_injection_in_sort_by_rejected(self, client, mock_controller):
        """Test that SQL injection attempts in sort_by are rejected."""
        injection_payloads = [
            "title; DROP TABLE documents; --",
            "created_at UNION SELECT password FROM users",
            "title' OR '1'='1",
            "invalid_field_with_injection"
        ]
        
        for payload in injection_payloads:
            response = client.get("/documents/", params={
                "sort_by": payload,
                "sort_order": "asc"
            })
            
            # Should return validation error
            assert response.status_code == 422
            error_detail = response.json()
            assert "detail" in error_detail
            # Should contain validation error about invalid enum value
            assert any("sort_by" in str(error) for error in error_detail["detail"])

    def test_sql_injection_in_sort_order_rejected(self, client, mock_controller):
        """Test that SQL injection attempts in sort_order are rejected."""
        injection_payloads = [
            "DESC; DROP TABLE documents; --", 
            "ASC UNION SELECT * FROM users",
            "invalid_order_injection"
        ]
        
        for payload in injection_payloads:
            response = client.get("/documents/", params={
                "sort_by": "title",
                "sort_order": payload
            })
            
            # Should return validation error
            assert response.status_code == 422
            error_detail = response.json()
            assert "detail" in error_detail
            # Should contain validation error about invalid enum value
            assert any("sort_order" in str(error) for error in error_detail["detail"])

    def test_dangerous_search_query_rejected(self, client, mock_controller):
        """Test that dangerous patterns in search queries are rejected."""
        dangerous_queries = [
            "search'; DROP TABLE documents; --",
            "query UNION SELECT password FROM users",
            "text; INSERT INTO malicious_table",
            "search/**/UNION/**/SELECT",
            "query -- malicious comment"
        ]
        
        for query in dangerous_queries:
            response = client.get("/documents/", params={
                "search_query": query,
                "sort_by": "title",
                "sort_order": "asc"
            })
            
            # Should return validation error  
            assert response.status_code == 422
            error_detail = response.json()
            assert "detail" in error_detail
            # Should mention dangerous pattern
            error_text = str(error_detail).lower()
            assert "dangerous pattern" in error_text

    def test_parameter_boundary_validation(self, client, mock_controller):
        """Test that parameter boundaries are enforced."""
        # Test invalid page numbers
        invalid_params_list = [
            {"page": 0, "per_page": 10},  # Page too low
            {"page": 10001, "per_page": 10},  # Page too high
            {"page": 1, "per_page": 0},  # Per_page too low
            {"page": 1, "per_page": 201},  # Per_page too high
        ]
        
        for invalid_params in invalid_params_list:
            response = client.get("/documents/", params=invalid_params)
            
            # Should return validation error
            assert response.status_code == 422
            error_detail = response.json()
            assert "detail" in error_detail

    def test_long_search_query_rejected(self, client, mock_controller):
        """Test that excessively long search queries are rejected."""
        # Create query longer than 500 characters
        long_query = "a" * 501
        
        response = client.get("/documents/", params={
            "search_query": long_query,
            "sort_by": "title",
            "sort_order": "asc"
        })
        
        # Should return validation error
        assert response.status_code == 422
        error_detail = response.json()
        assert "detail" in error_detail

    def test_enum_validation_edge_cases(self, client, mock_controller):
        """Test edge cases for enum validation."""
        # Test case sensitivity (should be handled by enum)
        response = client.get("/documents/", params={
            "sort_by": "TITLE",  # Wrong case
            "sort_order": "ASC"   # Wrong case
        })
        
        # Should return validation error for invalid enum values
        assert response.status_code == 422

    def test_special_characters_in_search_handled(self, client, mock_controller):
        """Test that special characters in search are handled safely."""
        # These should be safe special characters
        safe_queries = [
            "Machine Learning & AI",
            "C++ Programming (Advanced)",
            "Data Science - Introduction",
            "Algorithm #1: Sorting"
        ]
        
        for query in safe_queries:
            response = client.get("/documents/", params={
                "search_query": query,
                "sort_by": "title",
                "sort_order": "asc"
            })
            
            # Should not return validation error for safe special chars
            assert response.status_code != 422

    def test_controller_receives_secure_parameters(self, client, mock_controller):
        """Test that the controller receives properly validated parameters."""
        response = client.get("/documents/", params={
            "search_query": "Machine Learning",
            "sort_by": "title",
            "sort_order": "asc",
            "page": 1,
            "per_page": 10
        })
        
        # Verify controller was called with secure parameters
        mock_controller.get_documents.assert_called_once()
        call_args, call_kwargs = mock_controller.get_documents.call_args
        
        # Should receive the enum value, not raw string
        assert call_kwargs['sort_by'] == 'title'
        assert call_kwargs['search_query'] == 'Machine Learning'

    def test_error_responses_dont_leak_information(self, client, mock_controller):
        """Test that error responses don't leak sensitive information."""
        # Simulate internal error
        mock_controller.get_documents.side_effect = Exception("Internal database connection failed with credentials admin:password123")
        
        response = client.get("/documents/", params={
            "sort_by": "title",
            "sort_order": "asc"
        })
        
        # Should return 500 but not leak sensitive details
        assert response.status_code == 500
        error_detail = response.json()
        
        # Should not contain sensitive information
        error_text = str(error_detail).lower()
        assert "password" not in error_text
        assert "admin" not in error_text
        assert "credentials" not in error_text

    @pytest.mark.parametrize("sort_field", ["created_at", "updated_at", "last_accessed", "title", "file_size"])
    @pytest.mark.parametrize("sort_order", ["asc", "desc"])
    def test_all_valid_sort_combinations(self, client, mock_controller, sort_field, sort_order):
        """Test all valid sort field and order combinations."""
        response = client.get("/documents/", params={
            "sort_by": sort_field,
            "sort_order": sort_order
        })
        
        # Should not return validation error for any valid combination
        assert response.status_code != 422
        
        # Verify controller receives the parameters
        if mock_controller.get_documents.called:
            call_kwargs = mock_controller.get_documents.call_args[1]
            assert call_kwargs['sort_by'] == sort_field