"""
Modular Database Migrator

Drop-in replacement for the monolithic DatabaseMigrator class.
Provides backward compatibility while using the new modular migration system.
"""

import logging
from pathlib import Path
from typing import Any, Callable

from .connection import DatabaseConnection
from .migrations import MigrationManager, MigrationRunner, VersionTracker
from .migrations.base import MigrationError

logger = logging.getLogger(__name__)


class ModularDatabaseMigrator:
    """
    Modular database migrator that replaces the monolithic DatabaseMigrator.
    
    Provides the same interface as the original DatabaseMigrator while
    using the new modular migration system underneath.
    """
    
    CURRENT_VERSION = 7  # Matches the original system
    
    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize modular database migrator.
        
        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection
        
        # Initialize modular migration components
        self.manager = MigrationManager(db_connection)
        self.runner = MigrationRunner(self.manager)
        self.version_tracker = VersionTracker(db_connection)
        
        logger.info("Modular database migrator initialized")
        
    def get_current_version(self) -> int:
        """
        Get current database schema version.
        
        Returns:
            Current schema version number
        """
        return self.version_tracker.get_current_version()
        
    def set_version(self, version: int) -> None:
        """
        Set database schema version.
        
        Args:
            version: Version number to set
        """
        self.version_tracker.set_version(version)
        
    def needs_migration(self) -> bool:
        """
        Check if database needs migration.
        
        Returns:
            True if migration is needed
        """
        return self.manager.needs_migration()
        
    def migrate(self) -> bool:
        """
        Perform database migration to latest version.
        
        Returns:
            True if migration succeeded
            
        Raises:
            MigrationError: If migration fails
        """
        try:
            current_version = self.get_current_version()
            target_version = self.CURRENT_VERSION
            
            if current_version >= target_version:
                logger.info(
                    f"Database is already at version {current_version}, no migration needed"
                )
                return True
                
            logger.info(
                f"Migrating database from version {current_version} to {target_version}"
            )
            
            result = self.runner.migrate_to_version(target_version)
            
            if result["success"]:
                logger.info("Database migration completed successfully")
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Database migration failed: {error_msg}")
                raise MigrationError(f"Migration failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            raise MigrationError(f"Migration failed: {e}") from e
            
    def create_tables_if_not_exist(self) -> bool:
        """
        Create database tables if they don't exist.
        This is used for fresh installations.
        
        Returns:
            True if tables were created successfully
        """
        try:
            current_version = self.get_current_version()
            if current_version == 0:
                logger.info("Creating database schema for fresh installation")
                return self.migrate()
            else:
                logger.info(f"Database already exists at version {current_version}")
                return True
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise MigrationError(f"Table creation failed: {e}") from e
            
    def get_schema_info(self) -> dict[str, Any]:
        """
        Get information about current database schema.
        
        Returns:
            Dictionary with schema information
        """
        try:
            status = self.manager.get_migration_status()
            
            info: dict[str, Any] = {
                "current_version": status["current_version"],
                "target_version": status["target_version"],
                "needs_migration": status["needs_migration"],
                "tables": [],
            }
            
            # Get table information
            tables = self.db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            
            for table in tables:
                table_name = table["name"]
                
                # Get table info
                try:
                    table_info = self.db.fetch_all(f"PRAGMA table_info({table_name})")
                    columns = [
                        {
                            "name": col["name"],
                            "type": col["type"],
                            "notnull": bool(col["notnull"]),
                        }
                        for col in table_info
                    ]
                    
                    # Get row count
                    count_result = self.db.fetch_one(
                        f"SELECT COUNT(*) as count FROM {table_name}"
                    )
                    row_count = count_result["count"] if count_result else 0
                    
                    info["tables"].append(
                        {"name": table_name, "columns": columns, "row_count": row_count}
                    )
                except Exception as e:
                    logger.warning(f"Could not get info for table {table_name}: {e}")
                    
            return info
            
        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            return {"error": str(e)}
            
    def validate_schema(self) -> bool:
        """
        Validate that database schema is correct and complete.
        
        Returns:
            True if schema is valid
        """
        try:
            validation_result = self.runner.validate_schema()
            
            if validation_result["valid"]:
                logger.info("Database schema validation passed")
                return True
            else:
                logger.warning(f"Schema validation failed: {validation_result['issues']}")
                return False
                
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return False
            
    def get_performance_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive database performance statistics.
        
        Returns:
            Dictionary with performance metrics and analysis
        """
        try:
            # Get migration system status
            status = self.manager.get_migration_status()
            
            # Get basic database info  
            db_info = self._get_database_info()
            
            # Get table statistics
            table_stats = self._get_table_statistics()
            
            stats = {
                "migration_system": {
                    "current_version": status["current_version"],
                    "target_version": status["target_version"],
                    "needs_migration": status["needs_migration"],
                    "version_consistency": status["version_consistency"]
                },
                "database_info": db_info,
                "table_statistics": table_stats,
                "recent_migration_history": status.get("recent_history", [])
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get performance statistics: {e}")
            return {"error": str(e)}
            
    def _get_database_info(self) -> dict[str, Any]:
        """Get basic database information."""
        info = {}
        try:
            # Database file size  
            size_result = self.db.fetch_one(
                "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
            )
            info["database_size_bytes"] = size_result[0] if size_result else 0
            
            # Page information
            page_count = self.db.fetch_one("PRAGMA page_count")
            page_size = self.db.fetch_one("PRAGMA page_size")
            info["page_count"] = page_count[0] if page_count else 0
            info["page_size"] = page_size[0] if page_size else 0
            
            # Cache information
            cache_size = self.db.fetch_one("PRAGMA cache_size")
            info["cache_size_pages"] = cache_size[0] if cache_size else 0
            
            # Journal mode
            journal_mode = self.db.fetch_one("PRAGMA journal_mode")
            info["journal_mode"] = journal_mode[0] if journal_mode else "unknown"
            
        except Exception as e:
            logger.warning(f"Could not fetch database info: {e}")
            
        return info
        
    def _get_table_statistics(self) -> list[dict[str, Any]]:
        """Get statistics for each table."""
        table_stats = []
        try:
            tables = self.db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            
            for table_row in tables:
                table_name = table_row["name"]
                try:
                    # Row count
                    count_result = self.db.fetch_one(
                        f"SELECT COUNT(*) as count FROM {table_name}"
                    )
                    row_count = count_result["count"] if count_result else 0
                    
                    table_stats.append({
                        "table_name": table_name,
                        "row_count": row_count
                    })
                    
                except Exception as e:
                    logger.warning(f"Could not get statistics for table {table_name}: {e}")
                    table_stats.append({
                        "table_name": table_name,
                        "error": str(e)
                    })
                    
        except Exception as e:
            logger.warning(f"Could not fetch table statistics: {e}")
            
        return table_stats
        
    def optimize_database_performance(self) -> dict[str, Any]:
        """
        Run database optimization procedures.
        
        Returns:
            Dictionary with optimization results
        """
        results = {
            "operations_performed": [],
            "warnings": [],
            "success": False
        }
        
        try:
            # Update statistics for query optimizer
            logger.info("Updating database statistics...")
            self.db.execute("ANALYZE")
            results["operations_performed"].append("Updated query optimizer statistics")
            
            # Enable WAL mode if not already enabled
            journal_mode = self.db.fetch_one("PRAGMA journal_mode")
            if journal_mode and journal_mode[0] != "WAL":
                try:
                    self.db.execute("PRAGMA journal_mode=WAL")
                    results["operations_performed"].append("Enabled WAL mode for better concurrency")
                except Exception as e:
                    results["warnings"].append(f"Could not enable WAL mode: {e}")
                    
            # Enable foreign key constraints if not enabled
            fk_check = self.db.fetch_one("PRAGMA foreign_keys")
            if not fk_check or fk_check[0] != 1:
                self.db.execute("PRAGMA foreign_keys = ON")
                results["operations_performed"].append("Enabled foreign key constraints")
                
            results["success"] = True
            logger.info("Database optimization completed successfully")
            
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            results["error"] = str(e)
            
        return results
        
    # Additional methods for advanced functionality
    def rollback_to_version(self, target_version: int) -> bool:
        """
        Rollback database to a specific version.
        
        Args:
            target_version: Version to rollback to
            
        Returns:
            True if rollback succeeded
        """
        try:
            result = self.runner.migrate_to_version(target_version)
            
            if result["success"]:
                logger.info(f"Successfully rolled back to version {target_version}")
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Rollback failed: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
            
    def get_migration_plan(self, target_version: int | None = None) -> dict[str, Any]:
        """
        Get detailed migration execution plan.
        
        Args:
            target_version: Target version (default: latest)
            
        Returns:
            Dictionary with migration plan details
        """
        return self.manager.get_migration_plan(target_version)
        
    def get_migration_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Get migration history.
        
        Args:
            limit: Maximum number of history entries
            
        Returns:
            List of migration history entries
        """
        return self.version_tracker.get_migration_history(limit)


# Backward compatibility alias
DatabaseMigrator = ModularDatabaseMigrator