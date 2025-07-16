import pytest

from src.database.connection import DatabaseConnection
from src.database.migrations import DatabaseMigrator


@pytest.fixture
def db_connection():
    db = DatabaseConnection(db_path=":memory:")
    migrator = DatabaseMigrator(db)
    migrator.create_tables_if_not_exist()
    yield db
    db.close_connection()
