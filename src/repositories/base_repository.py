"""
Base Repository
Provides common functionality for all repository implementations.
Follows the Repository pattern to encapsulate data access logic.
"""

import logging
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

    def find_by_id(self, id: int) -> T | None:
        """
        Find entity by ID.
        Args:
            id: Primary key value
        Returns:
            Model object or None if not found
        """
        try:
            query = f"SELECT * FROM {self.get_table_name()} WHERE id = ?"
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
            query = f"SELECT * FROM {self.get_table_name()} ORDER BY id"
            if limit is not None:
                query += f" LIMIT {limit} OFFSET {offset}"
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
            query = f"SELECT COUNT(*) as count FROM {self.get_table_name()}"
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
            cols = ', '.join(columns)
            query = f"INSERT INTO {self.get_table_name()} ({cols}) VALUES ({placeholders})"
            self.db.execute(query, tuple(values))
            # Get the inserted ID and return updated model
            new_id = self.db.get_last_insert_id()
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
            query = f"UPDATE {self.get_table_name()} SET {set_clause} WHERE id = ?"
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
            query = f"DELETE FROM {self.get_table_name()} WHERE id = ?"
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
            query = f"SELECT 1 FROM {self.get_table_name()} WHERE id = ? LIMIT 1"
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
            query = f"SELECT * FROM {self.get_table_name()} WHERE {field} = ?"
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
