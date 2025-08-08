"""
Optimized Service Layer Test Configuration
Uses shared test utilities for better performance.
"""

import pytest

# Import optimized test utilities instead of creating duplicate fixtures
from tests.test_utils import db_manager


@pytest.fixture
def db_connection(request):
    """Optimized database connection for service tests."""
    test_name = f"service_{request.node.name}"
    db = db_manager.get_test_db(test_name)
    db_manager.clean_test_db(test_name)
    yield db
    # Cleanup handled by session-level cleanup
