"""
Base Migration Class

Provides common functionality for all migrations including:
- Transaction management
- Error handling and rollback
- Logging and progress tracking
- Database connection abstraction
- Validation and safety checks
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Raised when database migration fails."""
    pass


class BaseMigration(ABC):
    """
    Base class for all database migrations.
    
    Provides common functionality and enforces consistent patterns
    across all migrations while allowing for migration-specific logic.
    """

    def __init__(self, db_connection: Any) -> None:
        """
        Initialize migration with database connection.
        
        Args:
            db_connection: Database connection instance (from connection.py)
        """
        self.db = db_connection
        self.start_time = 0.0
        self.execution_time = 0.0
        
    @property
    @abstractmethod
    def version(self) -> int:
        """Migration version number (must be unique)."""
        pass
    
    @property
    @abstractmethod 
    def description(self) -> str:
        """Human-readable description of what this migration does."""
        pass
        
    @property
    def dependencies(self) -> list[int]:
        """List of migration versions that must run before this one."""
        return []
    
    @property
    def rollback_supported(self) -> bool:
        """Whether this migration supports rollback operations."""
        return False
        
    def pre_migrate_checks(self) -> bool:
        """
        Perform checks before running the migration.
        
        Returns:
            True if migration can proceed, False otherwise
            
        Raises:
            MigrationError: If critical pre-conditions are not met
        """
        # Check database connectivity
        try:
            self.db.execute("SELECT 1").fetchone()
        except Exception as e:
            raise MigrationError(f"Database connection check failed: {e}") from e
            
        # Check if migration has already been applied
        if self._is_already_applied():
            logger.warning(f"Migration {self.version} appears to already be applied")
            return False
            
        return True
        
    def post_migrate_checks(self) -> bool:
        """
        Perform validation after running the migration.
        
        Returns:
            True if migration completed successfully, False otherwise
        """
        return True
        
    @abstractmethod
    def up(self) -> None:
        """
        Apply the migration (upgrade database schema).
        
        This method should contain the actual migration logic.
        Must be implemented by each migration.
        """
        pass
        
    def down(self) -> None:
        """
        Rollback the migration (downgrade database schema).
        
        Default implementation raises an error.
        Override in migrations that support rollback.
        """
        if not self.rollback_supported:
            raise MigrationError(
                f"Migration {self.version} does not support rollback"
            )
        raise NotImplementedError("Rollback not implemented for this migration")
        
    def run(self) -> bool:
        """
        Execute the migration with full error handling and logging.
        
        Returns:
            True if migration completed successfully
            
        Raises:
            MigrationError: If migration fails
        """
        logger.info(f"Starting migration {self.version}: {self.description}")
        self.start_time = time.time()
        
        try:
            # Pre-migration checks
            if not self.pre_migrate_checks():
                logger.info(f"Migration {self.version} skipped (pre-checks failed)")
                return True
                
            # Execute migration within transaction
            with self.db.transaction():
                self.up()
                
            # Post-migration validation
            if not self.post_migrate_checks():
                raise MigrationError(
                    f"Migration {self.version} failed post-migration validation"
                )
                
            self.execution_time = time.time() - self.start_time
            logger.info(
                f"Migration {self.version} completed successfully "
                f"in {self.execution_time:.3f}s"
            )
            return True
            
        except Exception as e:
            self.execution_time = time.time() - self.start_time
            logger.error(
                f"Migration {self.version} failed after {self.execution_time:.3f}s: {e}"
            )
            raise MigrationError(f"Migration {self.version} failed: {e}") from e
            
    def rollback(self) -> bool:
        """
        Rollback the migration with full error handling and logging.
        
        Returns:
            True if rollback completed successfully
            
        Raises:
            MigrationError: If rollback fails
        """
        if not self.rollback_supported:
            raise MigrationError(
                f"Migration {self.version} does not support rollback"
            )
            
        logger.info(f"Rolling back migration {self.version}: {self.description}")
        self.start_time = time.time()
        
        try:
            with self.db.transaction():
                self.down()
                
            self.execution_time = time.time() - self.start_time
            logger.info(
                f"Migration {self.version} rollback completed successfully "
                f"in {self.execution_time:.3f}s"
            )
            return True
            
        except Exception as e:
            self.execution_time = time.time() - self.start_time
            logger.error(
                f"Migration {self.version} rollback failed after {self.execution_time:.3f}s: {e}"
            )
            raise MigrationError(f"Migration {self.version} rollback failed: {e}") from e
            
    def _is_already_applied(self) -> bool:
        """
        Check if this migration has already been applied.
        
        Returns:
            True if migration appears to be already applied
        """
        # This is a basic check - individual migrations can override
        # with more specific checks
        try:
            current_version = self._get_current_version()
            return current_version >= self.version
        except Exception:
            # If we can't determine version, assume not applied
            return False
            
    def _get_current_version(self) -> int:
        """Get current database schema version."""
        try:
            result = self.db.fetch_one("PRAGMA user_version")
            return result[0] if result else 0
        except Exception:
            return 0
            
    def _set_version(self, version: int) -> None:
        """Set database schema version."""
        try:
            self.db.execute(f"PRAGMA user_version = {version}")
            logger.debug(f"Database version set to {version}")
        except Exception as e:
            raise MigrationError(f"Cannot set database version: {e}") from e
            
    def execute_sql(self, sql: str, params: tuple | None = None) -> Any:
        """
        Execute SQL with proper error handling and logging.
        
        Args:
            sql: SQL statement to execute
            params: Optional parameters for the SQL statement
            
        Returns:
            Result of the SQL execution
        """
        try:
            return self.db.execute(sql, params)
        except Exception as e:
            logger.error(f"SQL execution failed: {sql[:100]}...")
            raise MigrationError(f"SQL execution failed: {e}") from e
            
    def execute_sql_file(self, file_path: str) -> None:
        """
        Execute SQL commands from a file.
        
        Args:
            file_path: Path to SQL file to execute
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
                
            # Split by semicolons and execute each statement
            statements = [stmt.strip() for stmt in sql_content.split(';')]
            statements = [stmt for stmt in statements if stmt]  # Remove empty statements
            
            for statement in statements:
                if statement:
                    self.execute_sql(statement)
                    
        except Exception as e:
            logger.error(f"Failed to execute SQL file {file_path}: {e}")
            raise MigrationError(f"SQL file execution failed: {e}") from e
            
    def create_table_if_not_exists(self, table_name: str, schema: str) -> None:
        """
        Create table if it doesn't exist.
        
        Args:
            table_name: Name of table to create
            schema: CREATE TABLE SQL statement
        """
        try:
            # Check if table exists
            result = self.db.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            
            if not result:
                self.execute_sql(schema)
                logger.info(f"Created table: {table_name}")
            else:
                logger.debug(f"Table {table_name} already exists")
                
        except Exception as e:
            raise MigrationError(f"Failed to create table {table_name}: {e}") from e
            
    def create_index_if_not_exists(self, index_name: str, schema: str) -> None:
        """
        Create index if it doesn't exist.
        
        Args:
            index_name: Name of index to create
            schema: CREATE INDEX SQL statement
        """
        try:
            # Check if index exists
            result = self.db.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,)
            )
            
            if not result:
                self.execute_sql(schema)
                logger.info(f"Created index: {index_name}")
            else:
                logger.debug(f"Index {index_name} already exists")
                
        except Exception as e:
            # Some index creation failures are acceptable (e.g., IF NOT EXISTS)
            logger.warning(f"Index creation warning for {index_name}: {e}")
            
    def get_migration_info(self) -> dict[str, Any]:
        """
        Get information about this migration.
        
        Returns:
            Dictionary with migration metadata
        """
        return {
            "version": self.version,
            "description": self.description,
            "dependencies": self.dependencies,
            "rollback_supported": self.rollback_supported,
            "execution_time": self.execution_time
        }