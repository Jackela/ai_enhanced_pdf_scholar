"""
Migration Version Tracker

Manages database schema version tracking and migration history.
Provides comprehensive version management with audit trail.
"""

import logging
from datetime import datetime
from typing import Any

from .base import MigrationError

logger = logging.getLogger(__name__)


class VersionTracker:
    """
    Tracks database schema versions and migration history.
    
    Provides robust version management with audit trail,
    rollback support, and migration validation.
    """
    
    def __init__(self, db_connection: Any) -> None:
        """
        Initialize version tracker.
        
        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection
        self._ensure_version_tables()
        
    def _ensure_version_tables(self) -> None:
        """Ensure version tracking tables exist."""
        try:
            # Main version tracking table
            version_table_sql = """
            CREATE TABLE IF NOT EXISTS migration_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER UNIQUE NOT NULL,
                description TEXT NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms REAL,
                rollback_supported BOOLEAN DEFAULT 0,
                checksum TEXT,
                metadata TEXT DEFAULT '{}'
            )
            """
            self.db.execute(version_table_sql)
            
            # Migration history table for audit trail
            history_table_sql = """
            CREATE TABLE IF NOT EXISTS migration_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                operation TEXT NOT NULL CHECK(operation IN ('apply', 'rollback')),
                description TEXT NOT NULL,
                started_at DATETIME NOT NULL,
                completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms REAL,
                success BOOLEAN NOT NULL DEFAULT 1,
                error_message TEXT,
                metadata TEXT DEFAULT '{}'
            )
            """
            self.db.execute(history_table_sql)
            
            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_migration_versions_version ON migration_versions(version)",
                "CREATE INDEX IF NOT EXISTS idx_migration_versions_applied ON migration_versions(applied_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_migration_history_version ON migration_history(version)",
                "CREATE INDEX IF NOT EXISTS idx_migration_history_operation ON migration_history(operation)",
                "CREATE INDEX IF NOT EXISTS idx_migration_history_completed ON migration_history(completed_at DESC)"
            ]
            
            for index_sql in indexes:
                try:
                    self.db.execute(index_sql)
                except Exception as e:
                    logger.warning(f"Could not create version tracking index: {e}")
                    
            logger.debug("Version tracking tables initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize version tracking tables: {e}")
            raise MigrationError(f"Version tracker initialization failed: {e}") from e
            
    def get_current_version(self) -> int:
        """
        Get current database schema version.
        
        Returns:
            Current version number, 0 if no migrations applied
        """
        try:
            # First check PRAGMA user_version for compatibility
            pragma_result = self.db.fetch_one("PRAGMA user_version")
            pragma_version = pragma_result[0] if pragma_result else 0
            
            # Check migration_versions table
            table_result = self.db.fetch_one(
                "SELECT MAX(version) as version FROM migration_versions"
            )
            table_version = table_result["version"] if table_result and table_result["version"] else 0
            
            # Use the higher of the two (for backward compatibility)
            current_version = max(pragma_version, table_version)
            
            logger.debug(f"Current schema version: {current_version}")
            return current_version
            
        except Exception as e:
            logger.warning(f"Could not determine current version: {e}")
            return 0
            
    def set_version(self, version: int) -> None:
        """
        Set database schema version.
        
        Args:
            version: Version number to set
        """
        try:
            # Update PRAGMA user_version for compatibility
            self.db.execute(f"PRAGMA user_version = {version}")
            logger.debug(f"Database version set to {version}")
        except Exception as e:
            logger.error(f"Failed to set database version: {e}")
            raise MigrationError(f"Cannot set database version: {e}") from e
            
    def record_migration_applied(
        self,
        version: int,
        description: str,
        execution_time_ms: float,
        rollback_supported: bool = False,
        checksum: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Record that a migration has been successfully applied.
        
        Args:
            version: Migration version number
            description: Migration description
            execution_time_ms: Execution time in milliseconds
            rollback_supported: Whether migration supports rollback
            checksum: Optional checksum for validation
            metadata: Optional metadata dictionary
        """
        try:
            # Insert into migration_versions table
            version_sql = """
            INSERT OR REPLACE INTO migration_versions 
            (version, description, applied_at, execution_time_ms, rollback_supported, checksum, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            import json
            metadata_json = json.dumps(metadata or {})
            
            self.db.execute(version_sql, (
                version, description, datetime.now().isoformat(),
                execution_time_ms, rollback_supported, checksum, metadata_json
            ))
            
            # Record in history
            self._record_history(
                version, "apply", description, execution_time_ms, True, None
            )
            
            # Update PRAGMA version
            self.set_version(version)
            
            logger.info(f"Recorded migration {version} as applied")
            
        except Exception as e:
            logger.error(f"Failed to record migration {version}: {e}")
            raise MigrationError(f"Cannot record migration: {e}") from e
            
    def record_migration_rollback(
        self,
        version: int,
        description: str,
        execution_time_ms: float
    ) -> None:
        """
        Record that a migration has been rolled back.
        
        Args:
            version: Migration version number
            description: Migration description
            execution_time_ms: Execution time in milliseconds
        """
        try:
            # Remove from migration_versions table
            self.db.execute(
                "DELETE FROM migration_versions WHERE version = ?",
                (version,)
            )
            
            # Record in history
            self._record_history(
                version, "rollback", description, execution_time_ms, True, None
            )
            
            # Update PRAGMA version to highest remaining version
            remaining_result = self.db.fetch_one(
                "SELECT MAX(version) as version FROM migration_versions"
            )
            new_version = remaining_result["version"] if remaining_result and remaining_result["version"] else 0
            self.set_version(new_version)
            
            logger.info(f"Recorded migration {version} as rolled back")
            
        except Exception as e:
            logger.error(f"Failed to record rollback for migration {version}: {e}")
            raise MigrationError(f"Cannot record rollback: {e}") from e
            
    def record_migration_failed(
        self,
        version: int,
        operation: str,
        description: str,
        execution_time_ms: float,
        error_message: str
    ) -> None:
        """
        Record that a migration operation failed.
        
        Args:
            version: Migration version number
            operation: Operation that failed ('apply' or 'rollback')
            description: Migration description
            execution_time_ms: Execution time in milliseconds
            error_message: Error message
        """
        try:
            self._record_history(
                version, operation, description, execution_time_ms, False, error_message
            )
            logger.info(f"Recorded failed {operation} for migration {version}")
        except Exception as e:
            logger.error(f"Failed to record migration failure: {e}")
            
    def _record_history(
        self,
        version: int,
        operation: str,
        description: str,
        execution_time_ms: float,
        success: bool,
        error_message: str | None
    ) -> None:
        """Record migration operation in history table."""
        history_sql = """
        INSERT INTO migration_history 
        (version, operation, description, started_at, execution_time_ms, success, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        # Calculate started_at from execution time
        now = datetime.now()
        started_at = datetime.fromtimestamp(
            now.timestamp() - (execution_time_ms / 1000)
        ).isoformat()
        
        self.db.execute(history_sql, (
            version, operation, description, started_at,
            execution_time_ms, success, error_message
        ))
        
    def get_applied_versions(self) -> list[int]:
        """
        Get list of all applied migration versions.
        
        Returns:
            Sorted list of applied version numbers
        """
        try:
            results = self.db.fetch_all(
                "SELECT version FROM migration_versions ORDER BY version"
            )
            return [row["version"] for row in results]
        except Exception as e:
            logger.warning(f"Could not fetch applied versions: {e}")
            return []
            
    def is_migration_applied(self, version: int) -> bool:
        """
        Check if a specific migration has been applied.
        
        Args:
            version: Migration version to check
            
        Returns:
            True if migration has been applied
        """
        try:
            result = self.db.fetch_one(
                "SELECT 1 FROM migration_versions WHERE version = ?",
                (version,)
            )
            return result is not None
        except Exception as e:
            logger.warning(f"Could not check migration {version}: {e}")
            return False
            
    def get_migration_info(self, version: int) -> dict[str, Any] | None:
        """
        Get information about a specific migration.
        
        Args:
            version: Migration version number
            
        Returns:
            Dictionary with migration info, None if not found
        """
        try:
            result = self.db.fetch_one(
                "SELECT * FROM migration_versions WHERE version = ?",
                (version,)
            )
            
            if result:
                import json
                info = dict(result)
                info["metadata"] = json.loads(info.get("metadata", "{}"))
                return info
            return None
            
        except Exception as e:
            logger.warning(f"Could not get info for migration {version}: {e}")
            return None
            
    def get_migration_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Get migration history.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            List of history entries, most recent first
        """
        try:
            results = self.db.fetch_all(
                "SELECT * FROM migration_history ORDER BY completed_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in results]
        except Exception as e:
            logger.warning(f"Could not fetch migration history: {e}")
            return []
            
    def cleanup_old_history(self, days_to_keep: int = 90) -> int:
        """
        Clean up old migration history entries.
        
        Args:
            days_to_keep: Number of days of history to keep
            
        Returns:
            Number of entries removed
        """
        try:
            result = self.db.execute(
                "DELETE FROM migration_history WHERE completed_at < date('now', '-{} days')".format(days_to_keep)
            )
            deleted_count = self.db.get_last_change_count()
            logger.info(f"Cleaned up {deleted_count} old migration history entries")
            return deleted_count
        except Exception as e:
            logger.warning(f"Could not cleanup migration history: {e}")
            return 0
            
    def validate_consistency(self) -> dict[str, Any]:
        """
        Validate consistency between version tracking methods.
        
        Returns:
            Dictionary with validation results
        """
        results = {
            "consistent": True,
            "pragma_version": 0,
            "table_version": 0,
            "issues": []
        }
        
        try:
            # Get PRAGMA version
            pragma_result = self.db.fetch_one("PRAGMA user_version")
            results["pragma_version"] = pragma_result[0] if pragma_result else 0
            
            # Get table version
            table_result = self.db.fetch_one(
                "SELECT MAX(version) as version FROM migration_versions"
            )
            results["table_version"] = table_result["version"] if table_result and table_result["version"] else 0
            
            # Check consistency
            if results["pragma_version"] != results["table_version"]:
                results["consistent"] = False
                results["issues"].append(
                    f"Version mismatch: PRAGMA={results['pragma_version']}, "
                    f"Table={results['table_version']}"
                )
                
            logger.debug(f"Version consistency check: {results}")
            
        except Exception as e:
            results["consistent"] = False
            results["issues"].append(f"Validation error: {e}")
            logger.warning(f"Version validation failed: {e}")
            
        return results