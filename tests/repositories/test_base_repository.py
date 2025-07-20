"""
Comprehensive Tests for BaseRepository
Tests the abstract base repository functionality by creating a concrete test implementation.
Covers all common repository operations and patterns including:
- CRUD operations
- Pagination and sorting
- Custom queries
- Error handling and edge cases
- Repository pattern compliance
"""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.database.connection import DatabaseConnection
from src.repositories.base_repository import BaseRepository


# Test model for BaseRepository testing
class TestModel:
    """Simple test model for BaseRepository testing."""

    def __init__(
        self,
        id: int = None,
        name: str = "",
        value: int = 0,
        created_at: datetime = None,
        metadata: str = "{}",
    ):
        self.id = id
        self.name = name
        self.value = value
        self.created_at = created_at or datetime.now()
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestModel":
        """Create model from dictionary."""
        created_at = None
        if data.get("created_at"):
            if isinstance(data["created_at"], str):
                created_at = datetime.fromisoformat(data["created_at"])
            else:
                created_at = data["created_at"]
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            value=data.get("value", 0),
            created_at=created_at,
            metadata=data.get("metadata", "{}"),
        )


# Concrete implementation of BaseRepository for testing
class TestRepository(BaseRepository[TestModel]):
    """Concrete test repository implementation."""

    def get_table_name(self) -> str:
        """Get the database table name."""
        return "test_models"

    def to_model(self, row: Dict[str, Any]) -> TestModel:
        """Convert database row to TestModel."""
        return TestModel.from_dict(row)

    def to_database_dict(self, model: TestModel) -> Dict[str, Any]:
        """Convert TestModel to database dictionary."""
        return model.to_dict()


class TestBaseRepository:
    """Comprehensive test suite for BaseRepository."""

    @classmethod
    def setup_class(cls):
        """Set up test database."""
        # Create temporary database
        cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_file.close()
        cls.db_path = cls.temp_db_file.name
        # Create database connection
        cls.db = DatabaseConnection(cls.db_path)
        # Initialize database schema
        cls._initialize_test_database()

    @classmethod
    def teardown_class(cls):
        """Clean up test database."""
        cls.db.close_all_connections()
        Path(cls.db_path).unlink(missing_ok=True)

    @classmethod
    def _initialize_test_database(cls):
        """Initialize database schema for testing."""
        cls.db.execute(
            """
            CREATE TABLE IF NOT EXISTS test_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            )
        """
        )

    def setup_method(self):
        """Set up for each test method."""
        self.repository = TestRepository(self.db)
        # Clear table for fresh test
        self.db.execute("DELETE FROM test_models")

    def _create_test_model(self, **kwargs) -> TestModel:
        """Create a test model with default values."""
        defaults = {"name": "Test Model", "value": 42, "metadata": "{}"}
        defaults.update(kwargs)
        return TestModel(**defaults)

    # ===== Abstract Method Implementation Tests =====
    def test_get_table_name_implementation(self):
        """Test that get_table_name is properly implemented."""
        assert self.repository.get_table_name() == "test_models"

    def test_to_model_implementation(self):
        """Test that to_model is properly implemented."""
        row_data = {
            "id": 1,
            "name": "Test",
            "value": 100,
            "created_at": "2023-01-01T10:00:00",
            "metadata": "{}",
        }
        model = self.repository.to_model(row_data)
        assert isinstance(model, TestModel)
        assert model.id == 1
        assert model.name == "Test"
        assert model.value == 100

    def test_to_database_dict_implementation(self):
        """Test that to_database_dict is properly implemented."""
        model = self._create_test_model(id=1, name="Test", value=100)
        db_dict = self.repository.to_database_dict(model)
        assert isinstance(db_dict, dict)
        assert db_dict["id"] == 1
        assert db_dict["name"] == "Test"
        assert db_dict["value"] == 100

    # ===== Base CRUD Operations Tests =====
    def test_create_model(self):
        """Test creating a new model."""
        model = self._create_test_model(name="New Model", value=123)
        created_model = self.repository.create(model)
        assert created_model is not None
        assert created_model.id is not None
        assert created_model.name == "New Model"
        assert created_model.value == 123

    def test_create_model_without_id(self):
        """Test creating model without ID (should be auto-generated)."""
        model = self._create_test_model(name="Auto ID Model")
        # Ensure ID is None
        model.id = None
        created_model = self.repository.create(model)
        assert created_model.id is not None
        assert created_model.name == "Auto ID Model"

    def test_find_by_id_success(self):
        """Test finding model by ID."""
        model = self._create_test_model(name="Find Test")
        created_model = self.repository.create(model)
        found_model = self.repository.find_by_id(created_model.id)
        assert found_model is not None
        assert found_model.id == created_model.id
        assert found_model.name == "Find Test"

    def test_find_by_id_not_found(self):
        """Test finding model by nonexistent ID."""
        found_model = self.repository.find_by_id(99999)
        assert found_model is None

    def test_update_model(self):
        """Test updating an existing model."""
        model = self._create_test_model(name="Original Name", value=100)
        created_model = self.repository.create(model)
        # Update the model
        created_model.name = "Updated Name"
        created_model.value = 200
        updated_model = self.repository.update(created_model)
        assert updated_model is not None
        assert updated_model.name == "Updated Name"
        assert updated_model.value == 200
        # Verify in database
        found_model = self.repository.find_by_id(created_model.id)
        assert found_model.name == "Updated Name"
        assert found_model.value == 200

    def test_update_model_without_id(self):
        """Test updating model without ID should raise error."""
        model = self._create_test_model(name="No ID Model")
        model.id = None
        with pytest.raises(ValueError, match="Cannot update entity without ID"):
            self.repository.update(model)

    def test_update_nonexistent_model(self):
        """Test updating nonexistent model should raise error."""
        model = self._create_test_model(id=99999, name="Nonexistent")
        with pytest.raises(ValueError, match="No test_models found with ID 99999"):
            self.repository.update(model)

    def test_delete_model(self):
        """Test deleting a model."""
        model = self._create_test_model(name="To Delete")
        created_model = self.repository.create(model)
        success = self.repository.delete(created_model.id)
        assert success is True
        # Verify deletion
        found_model = self.repository.find_by_id(created_model.id)
        assert found_model is None

    def test_delete_nonexistent_model(self):
        """Test deleting nonexistent model."""
        success = self.repository.delete(99999)
        assert success is False

    # ===== Find All and Pagination Tests =====
    def test_find_all_empty(self):
        """Test finding all models when none exist."""
        models = self.repository.find_all()
        assert models == []

    def test_find_all_with_models(self):
        """Test finding all models when some exist."""
        # Create multiple models
        for i in range(5):
            model = self._create_test_model(name=f"Model {i}", value=i * 10)
            self.repository.create(model)
        models = self.repository.find_all()
        assert len(models) == 5
        model_names = [m.name for m in models]
        assert "Model 0" in model_names
        assert "Model 4" in model_names

    def test_find_all_with_limit(self):
        """Test finding all models with limit."""
        # Create multiple models
        for i in range(10):
            model = self._create_test_model(name=f"Model {i}", value=i)
            self.repository.create(model)
        models = self.repository.find_all(limit=5)
        assert len(models) == 5

    def test_find_all_with_offset(self):
        """Test finding all models with offset."""
        # Create models in predictable order
        created_ids = []
        for i in range(10):
            model = self._create_test_model(name=f"Model {i}", value=i)
            created_model = self.repository.create(model)
            created_ids.append(created_model.id)
        # Get first 3 models
        first_batch = self.repository.find_all(limit=3, offset=0)
        # Get next 3 models
        second_batch = self.repository.find_all(limit=3, offset=3)
        assert len(first_batch) == 3
        assert len(second_batch) == 3
        # Verify no overlap
        first_ids = {m.id for m in first_batch}
        second_ids = {m.id for m in second_batch}
        assert first_ids.isdisjoint(second_ids)

    def test_find_all_with_limit_and_offset(self):
        """Test finding all models with both limit and offset."""
        # Create 10 models
        for i in range(10):
            model = self._create_test_model(name=f"Model {i}", value=i)
            self.repository.create(model)
        models = self.repository.find_all(limit=3, offset=5)
        assert len(models) == 3

    # ===== Count Tests =====
    def test_count_empty(self):
        """Test counting models when none exist."""
        count = self.repository.count()
        assert count == 0

    def test_count_with_models(self):
        """Test counting models when some exist."""
        # Create multiple models
        for i in range(7):
            model = self._create_test_model(name=f"Model {i}")
            self.repository.create(model)
        count = self.repository.count()
        assert count == 7

    # ===== Exists Tests =====
    def test_exists_true(self):
        """Test exists for existing model."""
        model = self._create_test_model(name="Exists Test")
        created_model = self.repository.create(model)
        exists = self.repository.exists(created_model.id)
        assert exists is True

    def test_exists_false(self):
        """Test exists for nonexistent model."""
        exists = self.repository.exists(99999)
        assert exists is False

    # ===== Find by Field Tests =====
    def test_find_by_field_success(self):
        """Test finding models by field value."""
        # Create models with different values
        model1 = self._create_test_model(name="Target", value=100)
        model2 = self._create_test_model(name="Other", value=200)
        model3 = self._create_test_model(name="Target", value=300)
        self.repository.create(model1)
        self.repository.create(model2)
        self.repository.create(model3)
        # Find by name
        results = self.repository.find_by_field("name", "Target")
        assert len(results) == 2
        for result in results:
            assert result.name == "Target"

    def test_find_by_field_not_found(self):
        """Test finding models by field when none match."""
        model = self._create_test_model(name="Test", value=100)
        self.repository.create(model)
        results = self.repository.find_by_field("name", "Nonexistent")
        assert results == []

    def test_find_by_field_numeric_value(self):
        """Test finding models by numeric field value."""
        model1 = self._create_test_model(name="Model 1", value=500)
        model2 = self._create_test_model(name="Model 2", value=600)
        model3 = self._create_test_model(name="Model 3", value=500)
        self.repository.create(model1)
        self.repository.create(model2)
        self.repository.create(model3)
        results = self.repository.find_by_field("value", 500)
        assert len(results) == 2
        for result in results:
            assert result.value == 500

    # ===== Custom Query Tests =====
    def test_execute_custom_query_simple(self):
        """Test executing simple custom query."""
        # Create test data
        for i in range(5):
            model = self._create_test_model(name=f"Model {i}", value=i * 10)
            self.repository.create(model)
        # Custom query for high values
        query = "SELECT * FROM test_models WHERE value >= ? ORDER BY value"
        results = self.repository.execute_custom_query(query, (30,))
        assert len(results) == 2  # values 30 and 40
        assert all(result.value >= 30 for result in results)
        assert results[0].value <= results[1].value  # Ordered

    def test_execute_custom_query_with_joins(self):
        """Test executing custom query with joins (simulated)."""
        # Create test data
        model1 = self._create_test_model(name="Alpha", value=100)
        model2 = self._create_test_model(name="Beta", value=200)
        self.repository.create(model1)
        self.repository.create(model2)
        # Custom query with aggregation
        query = """
        SELECT * FROM test_models
        WHERE value IN (
            SELECT value FROM test_models WHERE value > ?
        )
        ORDER BY value DESC
        """
        results = self.repository.execute_custom_query(query, (150,))
        assert len(results) == 1
        assert results[0].name == "Beta"
        assert results[0].value == 200

    def test_execute_custom_query_no_results(self):
        """Test executing custom query with no results."""
        model = self._create_test_model(name="Test", value=100)
        self.repository.create(model)
        query = "SELECT * FROM test_models WHERE value > ?"
        results = self.repository.execute_custom_query(query, (500,))
        assert results == []

    def test_execute_custom_query_without_params(self):
        """Test executing custom query without parameters."""
        model = self._create_test_model(name="Test", value=100)
        self.repository.create(model)
        query = "SELECT * FROM test_models ORDER BY id"
        results = self.repository.execute_custom_query(query)
        assert len(results) == 1
        assert results[0].name == "Test"

    # ===== Error Handling Tests =====
    @patch("src.repositories.base_repository.logger")
    def test_find_by_id_database_error(self, mock_logger):
        """Test error handling in find_by_id."""
        with patch.object(
            self.db, "fetch_one", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.find_by_id(1)
            mock_logger.error.assert_called_once()

    @patch("src.repositories.base_repository.logger")
    def test_find_all_database_error(self, mock_logger):
        """Test error handling in find_all."""
        with patch.object(
            self.db, "fetch_all", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.find_all()
            mock_logger.error.assert_called_once()

    @patch("src.repositories.base_repository.logger")
    def test_count_database_error(self, mock_logger):
        """Test error handling in count."""
        with patch.object(
            self.db, "fetch_one", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.count()
            mock_logger.error.assert_called_once()

    @patch("src.repositories.base_repository.logger")
    def test_create_database_error(self, mock_logger):
        """Test error handling in create."""
        model = self._create_test_model(name="Error Test")
        with patch.object(self.db, "execute", side_effect=Exception("Database error")):
            with pytest.raises(Exception, match="Database error"):
                self.repository.create(model)
            mock_logger.error.assert_called_once()

    @patch("src.repositories.base_repository.logger")
    def test_update_database_error(self, mock_logger):
        """Test error handling in update."""
        model = self._create_test_model(id=1, name="Update Test")
        with patch.object(self.db, "execute", side_effect=Exception("Database error")):
            with pytest.raises(Exception, match="Database error"):
                self.repository.update(model)
            mock_logger.error.assert_called_once()

    @patch("src.repositories.base_repository.logger")
    def test_delete_database_error(self, mock_logger):
        """Test error handling in delete."""
        with patch.object(self.db, "execute", side_effect=Exception("Database error")):
            with pytest.raises(Exception, match="Database error"):
                self.repository.delete(1)
            mock_logger.error.assert_called_once()

    @patch("src.repositories.base_repository.logger")
    def test_exists_database_error(self, mock_logger):
        """Test error handling in exists."""
        with patch.object(
            self.db, "fetch_one", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.exists(1)
            mock_logger.error.assert_called_once()

    @patch("src.repositories.base_repository.logger")
    def test_find_by_field_database_error(self, mock_logger):
        """Test error handling in find_by_field."""
        with patch.object(
            self.db, "fetch_all", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.find_by_field("name", "test")
            mock_logger.error.assert_called_once()

    @patch("src.repositories.base_repository.logger")
    def test_execute_custom_query_database_error(self, mock_logger):
        """Test error handling in execute_custom_query."""
        with patch.object(
            self.db, "fetch_all", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception, match="Database error"):
                self.repository.execute_custom_query("SELECT * FROM test_models")
            mock_logger.error.assert_called_once()

    # ===== Edge Cases and Special Scenarios =====
    def test_create_with_existing_id(self):
        """Test creating model with existing ID (should be removed)."""
        model = self._create_test_model(id=999, name="Existing ID")
        created_model = self.repository.create(model)
        # ID should be auto-generated, not 999
        assert created_model.id is not None
        assert created_model.id != 999
        assert created_model.name == "Existing ID"

    def test_update_model_preserves_id(self):
        """Test that update preserves the original ID."""
        model = self._create_test_model(name="Original")
        created_model = self.repository.create(model)
        original_id = created_model.id
        # Update the model normally (don't change ID)
        created_model.name = "Updated"
        updated_model = self.repository.update(created_model)
        # ID should remain the same
        assert updated_model.id == original_id
        assert updated_model.name == "Updated"

    def test_find_all_large_dataset(self):
        """Test find_all with larger dataset to verify performance."""
        # Create larger dataset
        for i in range(100):
            model = self._create_test_model(name=f"Model {i:03d}", value=i)
            self.repository.create(model)
        # Test various pagination scenarios
        all_models = self.repository.find_all()
        assert len(all_models) == 100
        first_page = self.repository.find_all(limit=25, offset=0)
        assert len(first_page) == 25
        last_page = self.repository.find_all(limit=25, offset=75)
        assert len(last_page) == 25
        # Verify no overlap
        first_ids = {m.id for m in first_page}
        last_ids = {m.id for m in last_page}
        assert first_ids.isdisjoint(last_ids)

    def test_count_consistency_with_find_all(self):
        """Test that count() is consistent with len(find_all())."""
        # Create test data
        for i in range(15):
            model = self._create_test_model(name=f"Model {i}")
            self.repository.create(model)
        count = self.repository.count()
        all_models = self.repository.find_all()
        assert count == len(all_models)
        assert count == 15

    # ===== Repository Pattern Compliance Tests =====
    def test_generic_type_compliance(self):
        """Test that repository properly handles generic type."""
        model = self._create_test_model(name="Type Test")
        created_model = self.repository.create(model)
        # All returned objects should be TestModel instances
        assert isinstance(created_model, TestModel)
        found_model = self.repository.find_by_id(created_model.id)
        assert isinstance(found_model, TestModel)
        all_models = self.repository.find_all()
        for m in all_models:
            assert isinstance(m, TestModel)

    def test_database_connection_usage(self):
        """Test that repository properly uses database connection."""
        # Verify database connection is set
        assert self.repository.db is not None
        assert self.repository.db == self.db
        # Test that operations use the connection
        model = self._create_test_model(name="DB Test")
        created_model = self.repository.create(model)
        # Verify in database directly
        direct_result = self.db.fetch_one(
            "SELECT * FROM test_models WHERE id = ?", (created_model.id,)
        )
        assert direct_result is not None
        assert direct_result["name"] == "DB Test"

    def test_abstract_method_enforcement(self):
        """Test that abstract methods must be implemented."""
        # This test verifies our concrete implementation works
        # In practice, trying to instantiate BaseRepository directly would fail
        # Verify all abstract methods are implemented
        assert hasattr(self.repository, "get_table_name")
        assert hasattr(self.repository, "to_model")
        assert hasattr(self.repository, "to_database_dict")
        # Verify they work correctly
        table_name = self.repository.get_table_name()
        assert isinstance(table_name, str)
        assert table_name == "test_models"
