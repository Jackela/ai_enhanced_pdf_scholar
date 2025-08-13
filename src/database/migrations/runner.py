"""
Migration Runner

High-level migration execution engine with comprehensive safety checks,
rollback support, and progress tracking.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from .base import MigrationError
from .manager import MigrationManager

logger = logging.getLogger(__name__)


class MigrationRunner:
    """
    High-level migration execution engine.

    Provides safe migration execution with progress tracking,
    rollback support, and comprehensive error handling.
    """

    def __init__(
        self,
        migration_manager: MigrationManager,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> None:
        """
        Initialize migration runner.

        Args:
            migration_manager: MigrationManager instance
            progress_callback: Optional callback for progress updates
                               Called with (current_step, total_steps, message)
        """
        self.manager = migration_manager
        self.progress_callback = progress_callback
        self.db = migration_manager.db
        self.version_tracker = migration_manager.version_tracker

    def migrate_to_latest(self) -> dict[str, Any]:
        """
        Migrate database to the latest available version.

        Returns:
            Dictionary with migration results
        """
        target_version = self.manager.get_target_version()
        return self.migrate_to_version(target_version)

    def migrate_to_version(self, target_version: int) -> dict[str, Any]:
        """
        Migrate database to a specific version.

        Args:
            target_version: Version to migrate to

        Returns:
            Dictionary with migration results
        """
        start_time = time.time()
        current_version = self.manager.get_current_version()

        result = {
            "success": False,
            "start_version": current_version,
            "target_version": target_version,
            "final_version": current_version,
            "migrations_applied": [],
            "migrations_failed": [],
            "execution_time_ms": 0,
            "error": None,
        }

        try:
            logger.info(
                f"Starting migration from version {current_version} to {target_version}"
            )

            if target_version == current_version:
                result["success"] = True
                result["execution_time_ms"] = (time.time() - start_time) * 1000
                logger.info("Database is already at target version")
                return result

            elif target_version > current_version:
                return self._migrate_up(target_version, result, start_time)
            else:
                return self._migrate_down(target_version, result, start_time)

        except Exception as e:
            result["error"] = str(e)
            result["execution_time_ms"] = (time.time() - start_time) * 1000
            result["final_version"] = self.manager.get_current_version()

            logger.error(f"Migration failed: {e}")
            return result

    def _migrate_up(
        self, target_version: int, result: dict, start_time: float
    ) -> dict[str, Any]:
        """Handle upgrade migrations."""
        try:
            # Validate migration plan
            validation_issues = self.manager.validate_migration_sequence(target_version)
            if validation_issues:
                raise MigrationError(
                    f"Migration validation failed: {validation_issues}"
                )

            # Get migrations to apply
            pending_migrations = [
                v
                for v in self.manager.get_available_versions()
                if self.manager.get_current_version() < v <= target_version
            ]

            if not pending_migrations:
                result["success"] = True
                result["execution_time_ms"] = (time.time() - start_time) * 1000
                logger.info("No migrations to apply")
                return result

            logger.info(
                f"Applying {len(pending_migrations)} migrations: {pending_migrations}"
            )

            # Apply each migration
            for i, version in enumerate(pending_migrations):
                self._report_progress(
                    i, len(pending_migrations), f"Applying migration {version}"
                )

                try:
                    migration = self.manager.create_migration(version)
                    migration_start = time.time()

                    # Check dependencies
                    for dep_version in migration.dependencies:
                        if not self.version_tracker.is_migration_applied(dep_version):
                            raise MigrationError(
                                f"Migration {version} depends on unapplied migration {dep_version}"
                            )

                    # Apply migration
                    migration.run()
                    execution_time = (time.time() - migration_start) * 1000

                    # Record success
                    self.version_tracker.record_migration_applied(
                        version,
                        migration.description,
                        execution_time,
                        migration.rollback_supported,
                    )

                    result["migrations_applied"].append(
                        {
                            "version": version,
                            "description": migration.description,
                            "execution_time_ms": execution_time,
                        }
                    )

                    logger.info(f"Successfully applied migration {version}")

                except Exception as e:
                    # Record failure
                    execution_time = (
                        (time.time() - migration_start) * 1000
                        if "migration_start" in locals()
                        else 0
                    )
                    self.version_tracker.record_migration_failed(
                        version,
                        "apply",
                        getattr(migration, "description", f"Migration {version}"),
                        execution_time,
                        str(e),
                    )

                    result["migrations_failed"].append(
                        {
                            "version": version,
                            "description": getattr(
                                migration, "description", f"Migration {version}"
                            ),
                            "error": str(e),
                            "execution_time_ms": execution_time,
                        }
                    )

                    raise MigrationError(f"Migration {version} failed: {e}") from e

            # Success
            result["success"] = True
            result["final_version"] = target_version
            result["execution_time_ms"] = (time.time() - start_time) * 1000

            self._report_progress(
                len(pending_migrations),
                len(pending_migrations),
                "Migration completed successfully",
            )

            logger.info(
                f"Successfully migrated from {result['start_version']} to {target_version} "
                f"in {result['execution_time_ms']:.1f}ms"
            )

            return result

        except Exception as e:
            result["error"] = str(e)
            result["execution_time_ms"] = (time.time() - start_time) * 1000
            result["final_version"] = self.manager.get_current_version()
            logger.error(f"Upgrade migration failed: {e}")
            return result

    def _migrate_down(
        self, target_version: int, result: dict, start_time: float
    ) -> dict[str, Any]:
        """Handle rollback migrations."""
        try:
            # Check if rollback is possible
            can_rollback, issues = self.manager.can_rollback_to(target_version)
            if not can_rollback:
                raise MigrationError(
                    f"Cannot rollback to version {target_version}: {issues}"
                )

            # Get rollback sequence
            rollback_sequence = self.manager.get_rollback_sequence(target_version)

            if not rollback_sequence:
                result["success"] = True
                result["execution_time_ms"] = (time.time() - start_time) * 1000
                logger.info("No rollbacks needed")
                return result

            logger.info(
                f"Rolling back {len(rollback_sequence)} migrations: {rollback_sequence}"
            )

            # Rollback each migration
            for i, version in enumerate(rollback_sequence):
                self._report_progress(
                    i, len(rollback_sequence), f"Rolling back migration {version}"
                )

                try:
                    migration = self.manager.create_migration(version)
                    migration_start = time.time()

                    # Perform rollback
                    migration.rollback()
                    execution_time = (time.time() - migration_start) * 1000

                    # Record rollback
                    self.version_tracker.record_migration_rollback(
                        version, migration.description, execution_time
                    )

                    result["migrations_applied"].append(
                        {
                            "version": version,
                            "description": f"Rollback: {migration.description}",
                            "execution_time_ms": execution_time,
                        }
                    )

                    logger.info(f"Successfully rolled back migration {version}")

                except Exception as e:
                    # Record failure
                    execution_time = (
                        (time.time() - migration_start) * 1000
                        if "migration_start" in locals()
                        else 0
                    )
                    self.version_tracker.record_migration_failed(
                        version,
                        "rollback",
                        getattr(migration, "description", f"Migration {version}"),
                        execution_time,
                        str(e),
                    )

                    result["migrations_failed"].append(
                        {
                            "version": version,
                            "description": f"Rollback: {getattr(migration, 'description', f'Migration {version}')}",
                            "error": str(e),
                            "execution_time_ms": execution_time,
                        }
                    )

                    raise MigrationError(
                        f"Rollback of migration {version} failed: {e}"
                    ) from e

            # Success
            result["success"] = True
            result["final_version"] = target_version
            result["execution_time_ms"] = (time.time() - start_time) * 1000

            self._report_progress(
                len(rollback_sequence),
                len(rollback_sequence),
                "Rollback completed successfully",
            )

            logger.info(
                f"Successfully rolled back from {result['start_version']} to {target_version} "
                f"in {result['execution_time_ms']:.1f}ms"
            )

            return result

        except Exception as e:
            result["error"] = str(e)
            result["execution_time_ms"] = (time.time() - start_time) * 1000
            result["final_version"] = self.manager.get_current_version()
            logger.error(f"Rollback migration failed: {e}")
            return result

    def create_tables_if_not_exist(self) -> dict[str, Any]:
        """
        Create database tables if they don't exist (for fresh installations).

        Returns:
            Dictionary with creation results
        """
        start_time = time.time()
        current_version = self.manager.get_current_version()

        result = {
            "success": False,
            "was_fresh_install": current_version == 0,
            "execution_time_ms": 0,
            "error": None,
        }

        try:
            if current_version == 0:
                logger.info("Creating database schema for fresh installation")
                migration_result = self.migrate_to_latest()
                result.update(migration_result)
            else:
                logger.info(f"Database already exists at version {current_version}")
                result["success"] = True

            result["execution_time_ms"] = (time.time() - start_time) * 1000
            return result

        except Exception as e:
            result["error"] = str(e)
            result["execution_time_ms"] = (time.time() - start_time) * 1000
            logger.error(f"Failed to create database tables: {e}")
            return result

    def validate_schema(self) -> dict[str, Any]:
        """
        Validate database schema consistency and integrity.

        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": False,
            "current_version": 0,
            "target_version": 0,
            "issues": [],
            "checks_performed": [],
        }

        try:
            # Basic version checks
            current_version = self.manager.get_current_version()
            target_version = self.manager.get_target_version()

            result["current_version"] = current_version
            result["target_version"] = target_version

            # Version consistency check
            consistency = self.version_tracker.validate_consistency()
            result["checks_performed"].append("version_consistency")

            if not consistency["consistent"]:
                result["issues"].extend(consistency["issues"])

            # Migration sequence validation
            validation_issues = self.manager.validate_migration_sequence()
            result["checks_performed"].append("migration_sequence")
            result["issues"].extend(validation_issues)

            # Check required tables exist
            required_tables = [
                "documents",
                "vector_indexes",
                "tags",
                "document_tags",
                "citations",
                "citation_relations",
                "users",
                "migration_versions",
            ]

            existing_tables = []
            try:
                table_results = self.db.fetch_all(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                existing_tables = [row["name"] for row in table_results]
                result["checks_performed"].append("required_tables")
            except Exception as e:
                result["issues"].append(f"Could not check tables: {e}")

            missing_tables = [t for t in required_tables if t not in existing_tables]
            if missing_tables:
                result["issues"].append(f"Missing required tables: {missing_tables}")

            # Check foreign key constraints
            try:
                fk_result = self.db.fetch_one("PRAGMA foreign_keys")
                if not fk_result or fk_result[0] != 1:
                    result["issues"].append("Foreign key constraints are not enabled")
                result["checks_performed"].append("foreign_keys")
            except Exception as e:
                result["issues"].append(f"Could not check foreign keys: {e}")

            # Determine overall validity
            result["valid"] = len(result["issues"]) == 0

            if result["valid"]:
                logger.info("Database schema validation passed")
            else:
                logger.warning(f"Database schema validation failed: {result['issues']}")

            return result

        except Exception as e:
            result["issues"].append(f"Validation error: {e}")
            logger.error(f"Schema validation failed: {e}")
            return result

    def _report_progress(self, current: int, total: int, message: str) -> None:
        """Report progress to callback if available."""
        if self.progress_callback:
            try:
                self.progress_callback(current, total, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

        logger.debug(f"Progress: {current}/{total} - {message}")

    def get_migration_plan_summary(self, target_version: int | None = None) -> str:
        """
        Get human-readable summary of migration plan.

        Args:
            target_version: Target version (default: latest)

        Returns:
            Human-readable migration plan summary
        """
        try:
            plan = self.manager.get_migration_plan(target_version)

            if plan.get("error"):
                return f"Migration plan error: {plan['error']}"

            current = plan["current_version"]
            target = plan["target_version"]
            direction = plan["direction"]

            if direction == "none":
                return f"Database is already at version {current} (no migration needed)"

            elif direction == "upgrade":
                migrations = plan["migrations_to_apply"]
                return (
                    f"Upgrade from version {current} to {target}\n"
                    f"Migrations to apply: {len(migrations)}\n"
                    + "\n".join(
                        [f"  {m['version']}: {m['description']}" for m in migrations]
                    )
                )

            elif direction == "rollback":
                migrations = plan["migrations_to_rollback"]
                return (
                    f"Rollback from version {current} to {target}\n"
                    f"Migrations to rollback: {len(migrations)}\n"
                    + "\n".join(
                        [
                            f"  {m['version']}: {m['description']} {'(supported)' if m['rollback_supported'] else '(NOT SUPPORTED)'}"
                            for m in migrations
                        ]
                    )
                )

            else:
                return f"Unknown migration direction: {direction}"

        except Exception as e:
            return f"Failed to generate migration plan: {e}"
