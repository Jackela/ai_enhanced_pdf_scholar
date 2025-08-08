"""
Migration Manager

Central manager for database migrations that handles discovery, validation,
and orchestration of migration operations.
"""

import importlib
import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Any

from .base import BaseMigration, MigrationError
from .version_tracker import VersionTracker

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Central manager for database migrations.
    
    Handles migration discovery, validation, dependency resolution,
    and provides high-level migration operations.
    """
    
    def __init__(self, db_connection: Any, migrations_path: str | None = None) -> None:
        """
        Initialize migration manager.
        
        Args:
            db_connection: Database connection instance
            migrations_path: Path to migrations directory (optional)
        """
        self.db = db_connection
        self.version_tracker = VersionTracker(db_connection)
        
        # Set migrations path
        if migrations_path:
            self.migrations_path = Path(migrations_path)
        else:
            # Default to migrations directory relative to this file
            self.migrations_path = Path(__file__).parent / "versions"
            
        # Migration registry
        self._migrations: dict[int, type[BaseMigration]] = {}
        self._discovery_completed = False
        
    def discover_migrations(self) -> None:
        """
        Discover all migration files and load migration classes.
        
        Scans the migrations directory for Python files matching the pattern:
        XXX_description.py where XXX is a 3-digit version number.
        """
        if self._discovery_completed:
            return
            
        logger.info(f"Discovering migrations in: {self.migrations_path}")
        
        try:
            # Ensure migrations directory exists
            self.migrations_path.mkdir(parents=True, exist_ok=True)
            
            # Scan for migration files
            for file_path in self.migrations_path.glob("*.py"):
                if file_path.name.startswith("__"):
                    continue  # Skip __init__.py and __pycache__
                    
                try:
                    self._load_migration_file(file_path)
                except Exception as e:
                    logger.error(f"Failed to load migration file {file_path}: {e}")
                    
            logger.info(f"Discovered {len(self._migrations)} migrations")
            self._discovery_completed = True
            
        except Exception as e:
            logger.error(f"Migration discovery failed: {e}")
            raise MigrationError(f"Cannot discover migrations: {e}") from e
            
    def _load_migration_file(self, file_path: Path) -> None:
        """Load migration class from a Python file."""
        try:
            # Extract version from filename (e.g., "001_initial_schema.py" -> 1)
            filename = file_path.stem
            if not filename[0:3].isdigit():
                logger.warning(f"Skipping file with invalid name format: {filename}")
                return
                
            version = int(filename[0:3])
            
            # Import the module with enhanced error handling
            spec = importlib.util.spec_from_file_location(filename, file_path)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not load spec for {file_path}")
                return
                
            module = importlib.util.module_from_spec(spec)
            
            # Add current directory to sys.path temporarily to help with imports
            import sys
            original_path = sys.path[:]
            try:
                # Add the migrations directory to help with BaseMigration imports
                migrations_dir = str(file_path.parent.parent)
                if migrations_dir not in sys.path:
                    sys.path.insert(0, migrations_dir)
                
                spec.loader.exec_module(module)
                
                # Find migration class in module
                migration_class = None
                classes_found = []
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj):
                        classes_found.append(name)
                        try:
                            # Check if this class inherits from BaseMigration by name
                            # This avoids import path issues
                            if (hasattr(obj, '__mro__') and 
                                any('BaseMigration' in str(cls) for cls in obj.__mro__) and
                                obj.__name__ != 'BaseMigration'):
                                migration_class = obj
                                break
                        except (TypeError, AttributeError):
                            continue
                            
                if migration_class is None:
                    logger.warning(f"No migration class found in {filename}. Classes found: {classes_found}")
                    return
                    
            finally:
                # Restore original sys.path
                sys.path[:] = original_path
                
            # Validate version matches
            temp_instance = migration_class(self.db)
            if temp_instance.version != version:
                raise MigrationError(
                    f"Version mismatch in {filename}: "
                    f"filename={version}, class={temp_instance.version}"
                )
                
            # Register migration
            self._migrations[version] = migration_class
            logger.debug(f"Loaded migration {version}: {temp_instance.description}")
            
        except Exception as e:
            logger.error(f"Error loading migration file {file_path}: {e}")
            raise
            
    def get_available_versions(self) -> list[int]:
        """
        Get list of all available migration versions.
        
        Returns:
            Sorted list of available version numbers
        """
        self.discover_migrations()
        return sorted(self._migrations.keys())
        
    def get_migration_class(self, version: int) -> type[BaseMigration] | None:
        """
        Get migration class for a specific version.
        
        Args:
            version: Migration version number
            
        Returns:
            Migration class or None if not found
        """
        self.discover_migrations()
        return self._migrations.get(version)
        
    def create_migration(self, version: int) -> BaseMigration:
        """
        Create migration instance for a specific version.
        
        Args:
            version: Migration version number
            
        Returns:
            Migration instance
            
        Raises:
            MigrationError: If migration version not found
        """
        migration_class = self.get_migration_class(version)
        if migration_class is None:
            raise MigrationError(f"Migration version {version} not found")
            
        return migration_class(self.db)
        
    def get_current_version(self) -> int:
        """Get current database schema version."""
        return self.version_tracker.get_current_version()
        
    def get_target_version(self) -> int:
        """Get highest available migration version."""
        versions = self.get_available_versions()
        return max(versions) if versions else 0
        
    def needs_migration(self) -> bool:
        """
        Check if database needs migration.
        
        Returns:
            True if migration is needed
        """
        current = self.get_current_version()
        target = self.get_target_version()
        return current < target
        
    def get_pending_migrations(self) -> list[int]:
        """
        Get list of migrations that need to be applied.
        
        Returns:
            Sorted list of pending migration versions
        """
        current_version = self.get_current_version()
        available_versions = self.get_available_versions()
        
        return [v for v in available_versions if v > current_version]
        
    def validate_migration_sequence(self, target_version: int | None = None) -> list[str]:
        """
        Validate migration sequence and dependencies.
        
        Args:
            target_version: Target version to validate up to (default: latest)
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        try:
            self.discover_migrations()
            available_versions = self.get_available_versions()
            
            if not available_versions:
                issues.append("No migrations available")
                return issues
                
            target = target_version or max(available_versions)
            current = self.get_current_version()
            
            # Check for gaps in version sequence
            expected_versions = list(range(1, target + 1))
            missing_versions = [v for v in expected_versions if v not in available_versions]
            
            if missing_versions:
                issues.append(f"Missing migration versions: {missing_versions}")
                
            # Check dependencies for each migration
            for version in available_versions:
                if version <= target:
                    try:
                        migration = self.create_migration(version)
                        
                        # Check if all dependencies are available
                        for dep_version in migration.dependencies:
                            if dep_version not in available_versions:
                                issues.append(
                                    f"Migration {version} depends on missing migration {dep_version}"
                                )
                            elif dep_version >= version:
                                issues.append(
                                    f"Migration {version} has invalid dependency on later migration {dep_version}"
                                )
                                
                    except Exception as e:
                        issues.append(f"Cannot instantiate migration {version}: {e}")
                        
            logger.debug(f"Migration validation found {len(issues)} issues")
            
        except Exception as e:
            issues.append(f"Validation error: {e}")
            
        return issues
        
    def get_rollback_sequence(self, target_version: int) -> list[int]:
        """
        Get sequence of migrations to roll back to reach target version.
        
        Args:
            target_version: Version to roll back to
            
        Returns:
            List of migration versions to roll back (in reverse order)
        """
        current_version = self.get_current_version()
        
        if target_version >= current_version:
            return []  # No rollback needed
            
        applied_versions = self.version_tracker.get_applied_versions()
        
        # Get versions to roll back (higher than target, in reverse order)
        rollback_versions = [v for v in applied_versions if v > target_version]
        rollback_versions.sort(reverse=True)
        
        return rollback_versions
        
    def can_rollback_to(self, target_version: int) -> tuple[bool, list[str]]:
        """
        Check if system can roll back to a specific version.
        
        Args:
            target_version: Target version to roll back to
            
        Returns:
            Tuple of (can_rollback, list_of_issues)
        """
        issues = []
        
        try:
            rollback_sequence = self.get_rollback_sequence(target_version)
            
            if not rollback_sequence:
                return True, []  # No rollback needed
                
            # Check if all migrations in rollback sequence support rollback
            for version in rollback_sequence:
                try:
                    migration = self.create_migration(version)
                    if not migration.rollback_supported:
                        issues.append(
                            f"Migration {version} does not support rollback"
                        )
                except Exception as e:
                    issues.append(f"Cannot check rollback support for migration {version}: {e}")
                    
        except Exception as e:
            issues.append(f"Rollback validation error: {e}")
            
        return len(issues) == 0, issues
        
    def get_migration_plan(self, target_version: int | None = None) -> dict[str, Any]:
        """
        Get detailed migration execution plan.
        
        Args:
            target_version: Target version (default: latest)
            
        Returns:
            Dictionary with migration plan details
        """
        try:
            current_version = self.get_current_version()
            available_versions = self.get_available_versions()
            target = target_version or (max(available_versions) if available_versions else 0)
            
            plan = {
                "current_version": current_version,
                "target_version": target,
                "direction": "upgrade" if target > current_version else ("rollback" if target < current_version else "none"),
                "migrations_to_apply": [],
                "migrations_to_rollback": [],
                "validation_issues": [],
                "estimated_time_ms": 0
            }
            
            if target > current_version:
                # Upgrade plan
                pending = [v for v in available_versions if current_version < v <= target]
                for version in sorted(pending):
                    migration = self.create_migration(version)
                    plan["migrations_to_apply"].append({
                        "version": version,
                        "description": migration.description,
                        "dependencies": migration.dependencies
                    })
                    
            elif target < current_version:
                # Rollback plan
                rollback_sequence = self.get_rollback_sequence(target)
                for version in rollback_sequence:
                    migration = self.create_migration(version)
                    plan["migrations_to_rollback"].append({
                        "version": version,
                        "description": migration.description,
                        "rollback_supported": migration.rollback_supported
                    })
                    
            # Validate the plan
            plan["validation_issues"] = self.validate_migration_sequence(target)
            
            return plan
            
        except Exception as e:
            return {
                "error": str(e),
                "current_version": self.get_current_version(),
                "target_version": target_version,
                "validation_issues": [f"Plan generation error: {e}"]
            }
            
    def get_migration_status(self) -> dict[str, Any]:
        """
        Get comprehensive migration system status.
        
        Returns:
            Dictionary with system status information
        """
        try:
            self.discover_migrations()
            
            current_version = self.get_current_version()
            available_versions = self.get_available_versions()
            applied_versions = self.version_tracker.get_applied_versions()
            
            status = {
                "current_version": current_version,
                "target_version": max(available_versions) if available_versions else 0,
                "needs_migration": self.needs_migration(),
                "available_migrations": len(available_versions),
                "applied_migrations": len(applied_versions),
                "pending_migrations": len(self.get_pending_migrations()),
                "version_consistency": self.version_tracker.validate_consistency(),
                "migrations_path": str(self.migrations_path),
                "discovery_completed": self._discovery_completed
            }
            
            # Recent migration history
            status["recent_history"] = self.version_tracker.get_migration_history(10)
            
            return status
            
        except Exception as e:
            return {
                "error": str(e),
                "current_version": self.get_current_version(),
                "needs_migration": False
            }