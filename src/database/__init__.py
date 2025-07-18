"""
Database Module
This package provides database connectivity, models, and migration utilities
for the AI Enhanced PDF Scholar application.
"""

from .connection import DatabaseConnection
from .migrations import DatabaseMigrator
from .models import DocumentModel, VectorIndexModel

__all__ = [
    "DatabaseConnection",
    "DatabaseMigrator",
    "DocumentModel",
    "VectorIndexModel",
]
