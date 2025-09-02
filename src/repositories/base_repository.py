"""
Base Repository
Provides common functionality for all repository implementations.
Follows the Repository pattern to encapsulate data access logic.
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from src.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)
# Generic type for model classes
T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    {
        "name": "BaseRepository",
        "version": "1.0.0",
        "description": "Abstract base class for all repository implementations.",
        "dependencies": ["DatabaseConnection"],
        "interface": {
            "inputs": ["database_connection: DatabaseConnection"],
            "outputs": "Common CRUD operations for database entities"
        }
    }
    Abstract base repository providing common database operations.
    All repositories should inherit from this class to ensure consistent interface.
    """

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize base repository.
        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection

    @abstractmethod
    def get_table_name(self) -> str:
        """
        Get the database table name for this repository.
        Returns:
            Table name string
        """
        pass

    @abstractmethod
    def to_model(self, row: dict[str, Any]) -> T:
        """
        Convert database row to model object.
        Args:
            row: Database row as dictionary
        Returns:
            Model object
        """
        pass

    @abstractmethod
    def to_database_dict(self, model: T) -> dict[str, Any]:
        """
        Convert model object to database dictionary.
        Args:
            model: Model object
        Returns:
            Dictionary suitable for database operations
        """
        pass

    def _is_valid_table_name(self, table_name: str) -> bool:
        """
        Validate table name to prevent SQL injection.
        Only allows alphanumeric characters and underscores.
        Args:
            table_name: Table name to validate
        Returns:
            True if valid, False otherwise
        """
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name))

    def find_by_id(self, id: int) -> T | None:
        """
        Find entity by ID.
        Args:
            id: Primary key value
        Returns:
            Model object or None if not found
        """
        try:
            # Use parameterized query with table name validation
            table_name = self.get_table_name()
            # Validate table name to prevent SQL injection
            if not self._is_valid_table_name(table_name):
                raise ValueError(f"Invalid table name: {table_name}")
            query = f"SELECT * FROM {table_name} WHERE id = ?"
            row = self.db.fetch_one(query, (id,))
            if row:
                return self.to_model(dict(row))
            return None
        except Exception as e:
            logger.error(f"Failed to find {self.get_table_name()} by ID {id}: {e}")
            raise

    def find_all(self, limit: int | None = None, offset: int = 0) -> list[T]:
        """
        Find all entities with optional pagination.
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
        Returns:
            List of model objects
        """
        try:
            table_name = self.get_table_name()
            if not self._is_valid_table_name(table_name):
                raise ValueError(f"Invalid table name: {table_name}")

            if limit is not None:
                # Use parameterized query for pagination
                query = f"SELECT * FROM {table_name} ORDER BY id LIMIT ? OFFSET ?"
                rows = self.db.fetch_all(query, (limit, offset))
            else:
                query = f"SELECT * FROM {table_name} ORDER BY id"
                rows = self.db.fetch_all(query)
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to find all {self.get_table_name()}: {e}")
            raise

    def count(self) -> int:
        """
        Count total number of entities.
        Returns:
            Total count
        """
        try:
            table_name = self.get_table_name()
            if not self._is_valid_table_name(table_name):
                raise ValueError(f"Invalid table name: {table_name}")
            query = f"SELECT COUNT(*) as count FROM {table_name}"
            result = self.db.fetch_one(query)
            return result["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to count {self.get_table_name()}: {e}")
            raise

    def create(self, model: T) -> T:
        """
        Create new entity.
        Args:
            model: Model object to create
        Returns:
            Created model with ID set
        """
        try:
            db_dict = self.to_database_dict(model)
            # Remove ID if present (will be auto-generated)
            db_dict.pop("id", None)
            # Build INSERT query
            columns = list(db_dict.keys())
            placeholders = ", ".join(["?" for _ in columns])
            values = [db_dict[col] for col in columns]
            cols = ", ".join(columns)
            table_name = self.get_table_name()
            if not self._is_valid_table_name(table_name):
                raise ValueError(f"Invalid table name: {table_name}")
            query = (
                f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders}) RETURNING id"
            )
            # Execute INSERT with RETURNING clause to get ID directly
            cursor = self.db.execute(query, tuple(values))
            result = cursor.fetchone()
            if result is None:
                raise RuntimeError(f"Failed to insert into {table_name}")
            new_id = result[0]
            # Retrieve the created model
            created_model = self.find_by_id(new_id)
            if created_model is None:
                raise RuntimeError(
                    f"Failed to retrieve created {self.get_table_name()} ID {new_id}"
                )
            return created_model
        except Exception as e:
            logger.error(f"Failed to create {self.get_table_name()}: {e}")
            raise

    def update(self, model: T) -> T:
        """
        Update existing entity.
        Args:
            model: Model object to update (must have ID)
        Returns:
            Updated model object
        """
        try:
            db_dict = self.to_database_dict(model)
            entity_id = db_dict.pop("id")
            if entity_id is None:
                raise ValueError("Cannot update entity without ID")
            # Build UPDATE query
            columns = list(db_dict.keys())
            set_clause = ", ".join([f"{col} = ?" for col in columns])
            values = [db_dict[col] for col in columns]
            values.append(entity_id)  # Add ID for WHERE clause
            table_name = self.get_table_name()
            if not self._is_valid_table_name(table_name):
                raise ValueError(f"Invalid table name: {table_name}")
            query = f"UPDATE {table_name} SET {set_clause} WHERE id = ?"
            result = self.db.execute(query, tuple(values))
            if result.rowcount == 0:
                raise ValueError(
                    f"No {self.get_table_name()} found with ID {entity_id}"
                )
            updated_model = self.find_by_id(entity_id)
            if updated_model is None:
                raise RuntimeError(
                    f"Failed to retrieve updated {self.get_table_name()} ID {entity_id}"
                )
            return updated_model
        except Exception as e:
            logger.error(f"Failed to update {self.get_table_name()}: {e}")
            raise

    def delete(self, id: int) -> bool:
        """
        Delete entity by ID.
        Args:
            id: Primary key value
        Returns:
            True if deleted, False if not found
        """
        try:
            table_name = self.get_table_name()
            if not self._is_valid_table_name(table_name):
                raise ValueError(f"Invalid table name: {table_name}")
            query = f"DELETE FROM {table_name} WHERE id = ?"
            result = self.db.execute(query, (id,))
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete {self.get_table_name()} ID {id}: {e}")
            raise

    def exists(self, id: int) -> bool:
        """
        Check if entity exists by ID.
        Args:
            id: Primary key value
        Returns:
            True if exists, False otherwise
        """
        try:
            table_name = self.get_table_name()
            if not self._is_valid_table_name(table_name):
                raise ValueError(f"Invalid table name: {table_name}")
            query = f"SELECT 1 FROM {table_name} WHERE id = ? LIMIT 1"
            result = self.db.fetch_one(query, (id,))
            return result is not None
        except Exception as e:
            logger.error(
                f"Failed to check existence of {self.get_table_name()} ID {id}: {e}"
            )
            raise

    def find_by_field(self, field: str, value: Any) -> list[T]:
        """
        Find entities by specific field value.
        Args:
            field: Field name to search
            value: Value to match
        Returns:
            List of matching model objects
        """
        try:
            table_name = self.get_table_name()
            if not self._is_valid_table_name(table_name):
                raise ValueError(f"Invalid table name: {table_name}")
            # Validate field name to prevent SQL injection
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', field):
                raise ValueError(f"Invalid field name: {field}")
            query = f"SELECT * FROM {table_name} WHERE {field} = ?"
            rows = self.db.fetch_all(query, (value,))
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(
                f"Failed to find {self.get_table_name()} by {field}={value}: {e}"
            )
            raise

    def execute_custom_query(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[T]:
        """
        Execute custom query and return model objects.
        Args:
            query: SQL query string
            params: Query parameters
        Returns:
            List of model objects
        """
        try:
            rows = self.db.fetch_all(query, params)
            return [self.to_model(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to execute custom query: {e}")
            raise
