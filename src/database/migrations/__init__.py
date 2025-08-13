"""
Modular Database Migration System

This package provides a modular, maintainable approach to database migrations,
replacing the monolithic migrations.py with versioned, individual migration files.

Key Features:
- Versioned migration files (001_initial_schema.py, 002_add_content_hash.py, etc.)
- Base migration class with common functionality
- Migration runner with rollback and validation capabilities
- Comprehensive testing framework
- Database integrity and safety checks
- Support for both SQLite and PostgreSQL
"""

from .base import BaseMigration, MigrationError
from .manager import MigrationManager
from .runner import MigrationRunner
from .version_tracker import VersionTracker

__all__ = [
    "BaseMigration",
    "MigrationError",
    "MigrationManager",
    "MigrationRunner",
    "VersionTracker",
]

# Current schema version - increment when adding new migrations
CURRENT_VERSION = 7

# Migration registry - automatically populated by migration discovery
MIGRATION_REGISTRY: dict[int, type[BaseMigration]] = {}


def register_migration(version: int, migration_class: type[BaseMigration]) -> None:
    """Register a migration class with the system."""
    MIGRATION_REGISTRY[version] = migration_class


def get_migration_class(version: int) -> type[BaseMigration] | None:
    """Get migration class by version number."""
    return MIGRATION_REGISTRY.get(version)


def get_available_versions() -> list[int]:
    """Get list of all available migration versions."""
    return sorted(MIGRATION_REGISTRY.keys())
