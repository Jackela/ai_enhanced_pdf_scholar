"""
Test Database Setup
Helper to create test database connections for UAT.
"""

import tempfile
from pathlib import Path
from src.database.connection import DatabaseConnection


def create_test_database() -> DatabaseConnection:
    """Create a test database connection for UAT."""
    # Use a temporary file for testing
    temp_dir = Path(tempfile.gettempdir()) / "ai_pdf_scholar_uat"
    temp_dir.mkdir(exist_ok=True)
    
    test_db_path = temp_dir / "test_database.sqlite"
    
    # Create database connection
    db = DatabaseConnection(str(test_db_path))
    
    return db


def create_memory_database() -> DatabaseConnection:
    """Create an in-memory database for testing."""
    return DatabaseConnection(":memory:")