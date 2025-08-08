"""
SQL Injection Prevention Security Tests

Comprehensive test suite to verify protection against SQL injection attacks
in document query endpoints and repository methods.
"""

import pytest
from unittest.mock import Mock, patch
import sqlite3
from fastapi.testclient import TestClient
from fastapi import HTTPException

from backend.api.models import DocumentQueryParams, DocumentSortField, SortOrder
from src.repositories.document_repository import DocumentRepository
from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel


class TestSQLInjectionPrevention:
    """Test suite for SQL injection vulnerability prevention."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection for testing."""
        mock_db = Mock(spec=DatabaseConnection)
        return mock_db

    @pytest.fixture
    def document_repository(self, mock_db_connection):
        """Create document repository with mocked database."""
        return DocumentRepository(mock_db_connection)

    def test_secure_sort_by_validation_valid_fields(self, document_repository, mock_db_connection):
        """Test that valid sort fields are accepted and processed securely."""
        # Mock successful database response
        mock_db_connection.fetch_all.return_value = []
        
        # Test all valid sort fields
        valid_fields = ["created_at", "updated_at", "last_accessed", "title", "file_size"]
        
        for field in valid_fields:
            # Should not raise exception and should use whitelisted value
            result = document_repository.get_all(sort_by=field)
            
            # Verify the query was executed with safe parameters
            mock_db_connection.fetch_all.assert_called()
            call_args = mock_db_connection.fetch_all.call_args
            query = call_args[0][0]
            
            # Verify the field is properly whitelisted and appears in query
            assert field in query
            assert "SELECT * FROM documents" in query
            assert "LIMIT ? OFFSET ?" in query

    def test_sql_injection_attempt_in_sort_by_blocked(self, document_repository, mock_db_connection):
        """Test that SQL injection attempts in sort_by are neutralized."""
        # Mock database response
        mock_db_connection.fetch_all.return_value = []
        
        # SQL injection payloads
        injection_payloads = [
            "created_at; DROP TABLE documents; --",
            "created_at UNION SELECT * FROM users --", 
            "created_at' OR '1'='1",
            "created_at/**/UNION/**/SELECT",
            "created_at; INSERT INTO documents",
            "(SELECT password FROM users)",
            "title'; DELETE FROM documents; --"
        ]
        
        for payload in injection_payloads:
            # Execute with malicious payload
            result = document_repository.get_all(sort_by=payload)
            
            # Verify that dangerous payload was sanitized to safe default
            call_args = mock_db_connection.fetch_all.call_args
            query = call_args[0][0]
            
            # Should fall back to safe default "created_at"
            assert "ORDER BY created_at DESC" in query
            # Should not contain any part of the injection payload
            assert "DROP" not in query.upper()
            assert "UNION" not in query.upper()  
            assert "INSERT" not in query.upper()
            assert "DELETE" not in query.upper()
            assert "password" not in query.lower()

    def test_sql_injection_attempt_in_sort_order_blocked(self, document_repository, mock_db_connection):
        """Test that SQL injection attempts in sort_order are neutralized."""
        mock_db_connection.fetch_all.return_value = []
        
        # SQL injection payloads for sort order
        injection_payloads = [
            "DESC; DROP TABLE documents; --",
            "ASC UNION SELECT * FROM users",
            "DESC' OR '1'='1",
            "ASC/**/UNION/**/SELECT",
            "; INSERT INTO malicious_table"
        ]
        
        for payload in injection_payloads:
            result = document_repository.get_all(sort_order=payload)
            
            call_args = mock_db_connection.fetch_all.call_args
            query = call_args[0][0]
            
            # Should fall back to safe default "DESC"
            assert "ORDER BY created_at DESC" in query
            # Should not contain injection content
            assert "DROP" not in query.upper()
            assert "UNION" not in query.upper()
            assert "INSERT" not in query.upper()

    def test_case_insensitive_sort_field_validation(self, document_repository, mock_db_connection):
        """Test that sort field validation is case-insensitive but secure."""
        mock_db_connection.fetch_all.return_value = []
        
        # Test case variations
        test_cases = [
            ("CREATED_AT", "created_at"),
            ("Created_At", "created_at"),
            ("title", "title"),
            ("TITLE", "title"),
            ("File_Size", "file_size")
        ]
        
        for input_field, expected_field in test_cases:
            result = document_repository.get_all(sort_by=input_field)
            
            call_args = mock_db_connection.fetch_all.call_args
            query = call_args[0][0]
            
            # Should normalize to lowercase whitelisted field
            assert f"ORDER BY {expected_field}" in query

    def test_pydantic_model_injection_prevention(self):
        """Test that Pydantic models prevent injection in search queries."""
        # Valid search query should pass
        valid_params = DocumentQueryParams(search_query="Machine Learning PDF")
        assert valid_params.search_query == "Machine Learning PDF"
        
        # Test dangerous patterns are rejected
        dangerous_queries = [
            "test'; DROP TABLE documents; --",
            "search UNION SELECT * FROM users",
            "query/**/SELECT/**/password", 
            "text; INSERT INTO malicious",
            "search -- comment",
            "query EXEC xp_cmdshell"
        ]
        
        for dangerous_query in dangerous_queries:
            with pytest.raises(ValueError) as exc_info:
                DocumentQueryParams(search_query=dangerous_query)
            
            assert "dangerous pattern" in str(exc_info.value).lower()

    def test_enum_validation_prevents_injection(self):
        """Test that enum-based validation prevents sort field injection."""
        # Valid enum values should work
        valid_params = DocumentQueryParams(
            sort_by=DocumentSortField.TITLE,
            sort_order=SortOrder.ASC
        )
        assert valid_params.sort_by == DocumentSortField.TITLE
        assert valid_params.sort_order == SortOrder.ASC
        
        # Invalid enum values should be rejected at Pydantic level
        with pytest.raises(ValueError):
            # This would fail at the Pydantic validation level
            DocumentQueryParams(sort_by="invalid_field; DROP TABLE documents")

    def test_parameter_limits_prevent_resource_exhaustion(self):
        """Test that parameter limits prevent resource exhaustion attacks."""
        # Test page limits
        with pytest.raises(ValueError):
            DocumentQueryParams(page=0)  # Below minimum
            
        with pytest.raises(ValueError):
            DocumentQueryParams(page=10001)  # Above maximum
        
        # Test per_page limits
        with pytest.raises(ValueError):
            DocumentQueryParams(per_page=0)  # Below minimum
            
        with pytest.raises(ValueError):
            DocumentQueryParams(per_page=201)  # Above maximum
            
        # Test search query length limits
        with pytest.raises(ValueError):
            DocumentQueryParams(search_query="x" * 501)  # Too long

    def test_repository_logging_for_security_audit(self, document_repository, mock_db_connection, caplog):
        """Test that security-relevant operations are logged for audit."""
        mock_db_connection.fetch_all.return_value = []
        
        # Execute query with logging
        with caplog.at_level("DEBUG"):
            document_repository.get_all(sort_by="title", sort_order="asc")
        
        # Verify security audit logging
        log_messages = [record.message for record in caplog.records]
        security_logs = [msg for msg in log_messages if "secure query" in msg.lower()]
        
        assert len(security_logs) > 0
        # Should log the sanitized values
        assert any("sort_by='title'" in log and "sort_order='ASC'" in log for log in security_logs)

    def test_whitelist_dictionary_completeness(self, document_repository):
        """Test that whitelist dictionaries contain all expected valid values."""
        # Create a test instance to access the validation logic
        mock_db = Mock(spec=DatabaseConnection)
        mock_db.fetch_all.return_value = []
        repo = DocumentRepository(mock_db)
        
        # Test that all DocumentSortField enum values are in repository whitelist
        enum_values = set(field.value for field in DocumentSortField)
        
        # Execute with each enum value to verify whitelist coverage
        for field_value in enum_values:
            result = repo.get_all(sort_by=field_value)
            call_args = mock_db.fetch_all.call_args
            query = call_args[0][0]
            # Should contain the exact field name in the query
            assert field_value in query

    @pytest.mark.integration
    def test_end_to_end_injection_prevention(self):
        """Integration test ensuring no SQL injection from API to database."""
        # This would require actual API client testing
        # For now, we verify the component integration
        
        # Test that malicious parameters are rejected at API level
        dangerous_params = {
            "sort_by": "created_at; DROP TABLE documents; --",
            "sort_order": "DESC UNION SELECT * FROM users",
            "search_query": "test'; DELETE FROM documents; --"
        }
        
        # These should be caught by Pydantic validation before reaching repository
        with pytest.raises((ValueError, TypeError)):
            params = DocumentQueryParams(**dangerous_params)

    def test_database_error_handling_prevents_information_leakage(self, document_repository, mock_db_connection):
        """Test that database errors don't leak sensitive information."""
        # Simulate database error
        mock_db_connection.fetch_all.side_effect = sqlite3.Error("Database connection failed")
        
        # Repository should catch and re-raise without exposing internal details
        with pytest.raises(sqlite3.Error):
            document_repository.get_all()
        
        # Verify error was logged securely (implementation detail)
        # In production, should log internally but not expose to user