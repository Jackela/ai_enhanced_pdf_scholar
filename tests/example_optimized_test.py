"""
Example Test File Using Optimized Infrastructure
Shows best practices for using the optimized test utilities.
"""

import pytest

from tests.test_utils import MockFactory


class TestOptimizedExample:
    """Example test class using optimized fixtures."""

    def test_database_operations(self, db_connection, mock_document_data):
        """Example database test with optimized fixtures."""
        # db_connection: Fast, shared database with automatic cleanup
        # mock_document_data: Cached mock data

        # Insert test data - use file_hash column and add required file_size
        db_connection.execute(
            "INSERT INTO documents (title, file_hash, file_size) VALUES (?, ?, ?)",
            (mock_document_data["title"], mock_document_data["content_hash"], 1024)
        )

        # Query data
        result = db_connection.fetch_one(
            "SELECT * FROM documents WHERE title = ?",
            (mock_document_data["title"],)
        )

        assert result is not None
        assert result["title"] == mock_document_data["title"]

    def test_with_mocks(self, mock_llama_index):
        """Example test using cached mock fixtures."""
        # mock_llama_index is pre-configured and cached

        mock_llama_index.query.return_value.response = "Test response"

        # Actually use the mock to test it
        result = mock_llama_index.query("test query")
        assert result.response == "Test response"

        # Verify the mock was called
        mock_llama_index.query.assert_called_once_with("test query")

    def test_performance_tracking(self, performance_tracker):
        """Example of performance monitoring."""
        import time

        with performance_tracker.measure("test_operation"):
            # Simulate some work
            time.sleep(0.1)

        # If this takes >500ms, it will be automatically flagged

    @pytest.mark.integration
    def test_integration_example(self, db_connection, test_data_directory):
        """Example integration test with proper marking."""
        # test_data_directory: Session-scoped temp directory

        test_file = test_data_directory / "test.txt"
        test_file.write_text("test content")

        # Test file operations with database
        assert test_file.exists()

    @pytest.mark.slow
    def test_complex_operation(self, isolated_db):
        """Example of test requiring complete isolation."""
        # Use isolated_db when you need complete database isolation
        # (Most tests should use db_connection for better performance)

        # Complex test that might affect other tests
        pass


# Example of custom fixture extending optimized infrastructure
@pytest.fixture
def specialized_mock():
    """Example of creating specialized fixture on top of optimized base."""
    mock = MockFactory.create_mock_llama_index()

    # Add specialized configuration
    mock.specialized_method = lambda x: f"specialized_{x}"

    return mock
