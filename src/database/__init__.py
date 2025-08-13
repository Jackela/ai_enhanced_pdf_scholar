"""
Database Module
This package provides database connectivity, models, and migration utilities
for the AI Enhanced PDF Scholar application.
"""

from .connection import DatabaseConnection
from .models import DocumentModel, VectorIndexModel
from .modular_migrator import ModularDatabaseMigrator as DatabaseMigrator

__all__ = [
    "DatabaseConnection",
    "DatabaseMigrator",
    "DocumentModel",
    "VectorIndexModel",
]
